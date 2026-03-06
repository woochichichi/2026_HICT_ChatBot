"""Docling 기반 PDF 파서. POC: 텍스트 블록 추출만."""

import hashlib
import json
import logging
from pathlib import Path

from backend.config import settings
from backend.models.parsed_document import Block, ParsedDocument

logger = logging.getLogger(__name__)

try:
    from docling.document_converter import DocumentConverter
except ImportError as e:
    raise ImportError(
        "Docling이 설치되지 않았습니다. pip install docling 후 다시 시도하세요."
    ) from e


def _doc_id_from_path(input_path: str) -> str:
    """파일 경로 기반 안정적 doc_id (sha1)."""
    path = Path(input_path).resolve()
    return hashlib.sha1(str(path).encode()).hexdigest()[:16]


def _collect_blocks_from_docling(doc) -> list[tuple[str, int | None]]:
    """DoclingDocument에서 (text, page_no) 리스트를 순서대로 수집."""
    blocks_raw: list[tuple[str, int | None]] = []
    try:
        for item, _level in doc.iterate_items():
            text = getattr(item, "text", None)
            if text is None:
                continue
            s = (text or "").strip()
            if not s:
                continue
            page = getattr(item, "page_no", None)
            blocks_raw.append((s, page))
    except Exception as e:
        logger.warning("iterate_items 실패, export_to_markdown 폴백: %s", e)
        full = doc.export_to_markdown() or ""
        for part in full.split("\n\n"):
            s = part.strip()
            if s:
                blocks_raw.append((s, None))
    return blocks_raw


def parse_pdf(input_path: str, *, doc_id: str | None = None) -> ParsedDocument:
    """PDF를 Docling으로 파싱해 ParsedDocument를 반환."""
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"파일 없음: {input_path}")
    if doc_id is None:
        doc_id = _doc_id_from_path(input_path)

    converter = DocumentConverter()
    result = converter.convert(str(path))
    doc = result.document

    title = getattr(doc, "name", None) or None
    pages = getattr(doc, "pages", None) or {}
    page_count = len(pages) if pages else None

    blocks_raw = _collect_blocks_from_docling(doc)
    blocks = [
        Block(text=t, page=pg, order=i)
        for i, (t, pg) in enumerate(blocks_raw)
    ]

    meta = {
        "parser": "docling",
        "doc_type": "pdf",
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
    """ParsedDocument를 {DATA_DIR}/processed/{doc_id}/docling.json 에 저장. meta.output_path 설정 후 저장 경로 반환."""
    base = Path(data_dir or settings.DATA_DIR)
    out_dir = base / "processed" / parsed.doc_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "docling.json"

    parsed_dict = parsed.model_dump()
    parsed_dict["meta"] = {**parsed.meta, "output_path": str(out_path)}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed_dict, f, ensure_ascii=False, indent=2)

    return str(out_path)
