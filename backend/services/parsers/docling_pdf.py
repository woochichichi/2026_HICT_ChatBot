"""Docling 기반 PDF 파서. 업무편람 텍스트·표 추출 → Vector DB 저장용."""

import hashlib
import json
import logging
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


def _collect_blocks_from_docling(doc) -> list[Block]:
    """DoclingDocument에서 블록을 타입별로 수집.

    - SectionHeaderItem → block_type="section_header", heading_level 포함
    - TextItem(paragraph/list_item 등) → block_type="text"
    - TableItem → block_type="table", 마크다운으로 변환
    - 머리글/바닥글은 제외
    """
    blocks: list[Block] = []
    order = 0

    try:
        for item, _level in doc.iterate_items():
            label = getattr(item, "label", None)
            if label in _SKIP_LABELS:
                continue

            if isinstance(item, SectionHeaderItem):
                text = (item.text or "").strip()
                if not text:
                    continue
                blocks.append(Block(
                    text=text,
                    block_type="section_header",
                    page=_get_page_no(item),
                    order=order,
                    heading_level=getattr(item, "level", None),
                ))
                order += 1

            elif isinstance(item, TableItem):
                text = _table_to_text(item)
                if not text:
                    continue
                caption_parts = []
                for cap_ref in getattr(item, "captions", []):
                    cap_item = doc.get_ref(cap_ref) if hasattr(doc, "get_ref") else None
                    if cap_item and hasattr(cap_item, "text"):
                        caption_parts.append(cap_item.text.strip())
                if caption_parts:
                    text = "\n".join(caption_parts) + "\n\n" + text
                blocks.append(Block(
                    text=text,
                    block_type="table",
                    page=_get_page_no(item),
                    order=order,
                ))
                order += 1

            elif isinstance(item, TextItem):
                text = (item.text or "").strip()
                if not text:
                    continue
                blocks.append(Block(
                    text=text,
                    block_type="text",
                    page=_get_page_no(item),
                    order=order,
                ))
                order += 1

    except Exception as e:
        logger.warning("iterate_items 실패, export_to_markdown 폴백: %s", e)
        full = doc.export_to_markdown() or ""
        for part in full.split("\n\n"):
            s = part.strip()
            if s:
                blocks.append(Block(text=s, block_type="text", page=None, order=order))
                order += 1

    return blocks


def parse_pdf(input_path: str, *, doc_id: str | None = None) -> ParsedDocument:
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
        title=title,
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
