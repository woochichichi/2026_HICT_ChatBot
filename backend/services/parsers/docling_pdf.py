"""Docling 기반 PDF 파서. 문서 텍스트·표 추출 → VectorDB 적재용."""

import hashlib
import json
import logging
import re
from pathlib import Path

from backend.config import settings
from backend.models.parsed_document import Block, ParsedDocument

logger = logging.getLogger(__name__)

try:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        TableFormerMode,
        TableStructureOptions,
        ThreadedPdfPipelineOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import DocItemLabel, SectionHeaderItem, TableItem, TextItem
except ImportError as e:
    raise ImportError(
        "Docling이 설치되지 않았습니다. pip install docling 후 다시 시도하세요."
    ) from e


_SKIP_LABELS = frozenset({
    DocItemLabel.PAGE_HEADER,
    DocItemLabel.PAGE_FOOTER,
})

# ---------- heading depth 감지 ----------

_DEPTH_PATTERNS = [
    (re.compile(r"^\d+[\)\.]\s"), 1),       # "3) ..." "1. ..."
    (re.compile(r"^[가-힣][\.\)]\s"), 2),    # "가. ..." "나) ..."
    (re.compile(r"^[ㄱ-ㅎ][\.\)]\s"), 3),    # "ㄱ. ..." "ㄴ) ..."
]


def _detect_heading_depth(text: str) -> int:
    """한국어 개조식 번호 패턴으로 heading 깊이 추정."""
    t = text.strip()
    for pat, depth in _DEPTH_PATTERNS:
        if pat.match(t):
            return depth
    return 2


def _update_heading_stack(
    stack: list[tuple[int, str]], depth: int, text: str,
) -> None:
    """heading stack을 현재 depth에 맞게 정리 후 push."""
    while stack and stack[-1][0] >= depth:
        stack.pop()
    stack.append((depth, text))


def _get_hierarchy_path(stack: list[tuple[int, str]]) -> list[str] | None:
    """heading stack → hierarchy_path. depth 1(문서 제목급)은 제외."""
    path = [text for depth, text in stack if depth > 1]
    return path or None


def _get_heading_context(stack: list[tuple[int, str]]) -> str | None:
    """가장 구체적인(마지막) heading 텍스트 반환. canonical_text 생성용."""
    for depth, text in reversed(stack):
        if depth > 1:
            return text
    return None


# ---------- 마크다운 표 파싱 ----------

def _split_md_row(line: str) -> list[str]:
    """파이프(|) 구분 마크다운 행 → 셀 리스트."""
    cells = [c.strip() for c in line.split("|")]
    if cells and not cells[0]:
        cells = cells[1:]
    if cells and not cells[-1]:
        cells = cells[:-1]
    return cells


def _parse_md_table_rows(md_text: str) -> tuple[list[str], list[list[str]]]:
    """마크다운 테이블 → (headers, data_rows)."""
    lines = [l for l in md_text.strip().splitlines() if l.strip()]
    if len(lines) < 3:
        return [], []

    headers = _split_md_row(lines[0])
    rows = []
    for line in lines[1:]:
        if re.match(r"^[\|\-\:\s]+$", line):
            continue
        cells = _split_md_row(line)
        if any(c for c in cells):
            rows.append(cells)
    return headers, rows


def _build_canonical_text(
    headers: list[str],
    row_cells: list[str],
    heading_context: str | None,
) -> str | None:
    """표 행 → 검색용 자연어 문장.

    heading_context가 있으면 "{주체}의 {맥락}는 {값}이다." 형태로 생성.
    """
    paired = [(h, v.strip()) for h, v in zip(headers, row_cells) if v.strip()]
    if not paired:
        return None

    if len(paired) >= 2 and heading_context:
        seen: set[str] = set()
        subjects: list[str] = []
        for _, v in paired[:-1]:
            if v not in seen:
                subjects.append(v)
                seen.add(v)
        subject = " ".join(subjects)
        value = paired[-1][1]
        # "ㄱ. 고객실명번호(식별번호)" → "고객실명번호"
        ctx = re.sub(r"^[ㄱ-ㅎ가-힣\d]+[\.\)]\s*", "", heading_context)
        ctx = re.sub(r"[\(（].*?[\)）]", "", ctx).strip()
        if ctx:
            return f"{subject}의 {ctx}는 {value}이다."

    return ", ".join(f"{h}: {v}" for h, v in paired)


# ---------- converter / 유틸 ----------

def _build_converter() -> DocumentConverter:
    """업무편람 PDF에 최적화된 DocumentConverter를 생성."""
    pipeline_opts = ThreadedPdfPipelineOptions(
        do_table_structure=True,
        table_structure_options=TableStructureOptions(
            do_cell_matching=True,
            mode=TableFormerMode.ACCURATE,
        ),
        do_ocr=True,
    )
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_opts,
            ),
        },
    )


def _doc_id_from_path(input_path: str) -> str:
    """파일 경로 기반 안정적 doc_id (sha1)."""
    path = Path(input_path).resolve()
    return hashlib.sha1(str(path).encode()).hexdigest()[:16]


def _get_page_no(item) -> int | None:
    """ProvenanceItem에서 페이지 번호를 추출."""
    prov = getattr(item, "prov", None)
    if prov and len(prov) > 0:
        return prov[0].page_no
    return None


def _table_to_text(table: TableItem) -> str:
    """TableItem을 마크다운 테이블 문자열로 변환.
    마크다운 변환 실패 시 셀 텍스트를 탭 구분으로 폴백.
    """
    try:
        md = table.export_to_markdown()
        if md and md.strip():
            return md.strip()
    except Exception:
        logger.debug("export_to_markdown 실패, 폴백 시도")

    try:
        df = table.export_to_dataframe()
        if df is not None and not df.empty:
            return df.to_markdown(index=False)
    except Exception:
        logger.debug("export_to_dataframe 실패")

    return ""


# ---------- 블록 수집 ----------

def _collect_blocks_from_docling(doc) -> list[Block]:
    """DoclingDocument → Block 리스트.

    - SectionHeaderItem → "heading" + heading stack 갱신
    - TextItem → "paragraph"
    - TableItem → "table"(전체 마크다운) + "table_row"(행별 분리)
    """
    blocks: list[Block] = []
    order = 0
    heading_stack: list[tuple[int, str]] = []

    try:
        for item, _level in doc.iterate_items():
            label = getattr(item, "label", None)
            if label in _SKIP_LABELS:
                continue

            if isinstance(item, SectionHeaderItem):
                text = (item.text or "").strip()
                if not text:
                    continue
                depth = _detect_heading_depth(text)
                _update_heading_stack(heading_stack, depth, text)
                blocks.append(Block(
                    text=text,
                    block_type="heading",
                    page=_get_page_no(item),
                    order=order,
                    heading_level=depth,
                    hierarchy_path=_get_hierarchy_path(heading_stack),
                ))
                order += 1

            elif isinstance(item, TableItem):
                md_text = _table_to_text(item)
                if not md_text:
                    continue

                hierarchy = _get_hierarchy_path(heading_stack)
                page = _get_page_no(item)

                # caption 처리
                caption_parts = []
                for cap_ref in getattr(item, "captions", []):
                    cap_item = doc.get_ref(cap_ref) if hasattr(doc, "get_ref") else None
                    if cap_item and hasattr(cap_item, "text"):
                        caption_parts.append(cap_item.text.strip())
                full_md = ("\n".join(caption_parts) + "\n\n" + md_text) if caption_parts else md_text

                # table 블록: 전체 마크다운
                blocks.append(Block(
                    text=full_md,
                    block_type="table",
                    page=page,
                    order=order,
                    hierarchy_path=hierarchy,
                ))
                order += 1

                # table_row 블록: 행별 분리 + canonical_text
                headers, rows = _parse_md_table_rows(md_text)
                heading_ctx = _get_heading_context(heading_stack)
                for row_cells in rows:
                    row_text = " | ".join(c for c in row_cells if c)
                    if not row_text.strip():
                        continue
                    blocks.append(Block(
                        text=row_text,
                        block_type="table_row",
                        page=page,
                        order=order,
                        hierarchy_path=hierarchy,
                        canonical_text=_build_canonical_text(headers, row_cells, heading_ctx),
                    ))
                    order += 1

            elif isinstance(item, TextItem):
                text = (item.text or "").strip()
                if not text:
                    continue
                blocks.append(Block(
                    text=text,
                    block_type="paragraph",
                    page=_get_page_no(item),
                    order=order,
                    hierarchy_path=_get_hierarchy_path(heading_stack),
                ))
                order += 1

    except Exception as e:
        logger.warning("iterate_items 실패, export_to_markdown 폴백: %s", e)
        full = doc.export_to_markdown() or ""
        for part in full.split("\n\n"):
            s = part.strip()
            if s:
                blocks.append(Block(text=s, block_type="paragraph", page=None, order=order))
                order += 1

    return blocks


# ---------- 공개 API ----------

def parse_pdf(
    input_path: str,
    *,
    doc_id: str | None = None,
    doc_type: str = "manual",
    document_path: list[str] | None = None,
) -> ParsedDocument:
    """PDF를 Docling으로 파싱해 ParsedDocument를 반환."""
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"파일 없음: {input_path}")
    if doc_id is None:
        doc_id = _doc_id_from_path(input_path)

    converter = _build_converter()
    result = converter.convert(str(path))
    doc = result.document

    title = getattr(doc, "name", None) or None
    pages = getattr(doc, "pages", None) or {}
    page_count = len(pages) if pages else None

    blocks = _collect_blocks_from_docling(doc)

    table_count = sum(1 for b in blocks if b.block_type == "table")
    logger.info(
        "파싱 완료: %s — %d 블록 (표 %d개), %s 페이지",
        path.name, len(blocks), table_count, page_count or "?",
    )

    meta = {
        "parser": "docling",
        "doc_type": "pdf",
        "table_count": table_count,
        "output_path": None,
    }

    return ParsedDocument(
        doc_id=doc_id,
        source_path=str(path.resolve()),
        doc_type=doc_type,
        title=title,
        document_path=document_path,
        page_count=page_count,
        blocks=blocks,
        meta=meta,
    )


def save_parsed_document(parsed: ParsedDocument, data_dir: str | None = None) -> str:
    """ParsedDocument를 {DATA_DIR}/processed/{doc_id}/docling.json 에 저장."""
    base = Path(data_dir or settings.DATA_DIR)
    out_dir = base / "processed" / parsed.doc_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "docling.json"

    parsed_dict = parsed.model_dump()
    parsed_dict["meta"] = {**parsed.meta, "output_path": str(out_path)}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed_dict, f, ensure_ascii=False, indent=2)

    return str(out_path)
