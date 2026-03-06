"""Docling PDF 파서 최소 테스트. 샘플 PDF 없으면 skip."""

import pytest
from pathlib import Path

# 프로젝트 루트 기준
ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PDF = ROOT / "data" / "raw" / "sample.pdf"


@pytest.mark.skipif(not SAMPLE_PDF.is_file(), reason="data/raw/sample.pdf 없음")
def test_parse_pdf_returns_parsed_document():
    from backend.services.parsers.docling_pdf import parse_pdf, save_parsed_document

    parsed = parse_pdf(str(SAMPLE_PDF))
    assert parsed.doc_id
    assert parsed.source_path
    assert parsed.meta.get("parser") == "docling"
    assert parsed.meta.get("doc_type") == "pdf"
    assert isinstance(parsed.blocks, list)
    for i, b in enumerate(parsed.blocks):
        assert b.text
        assert b.order == i

    out_path = save_parsed_document(parsed)
    assert Path(out_path).exists()
    assert parsed.meta.get("output_path") == out_path
