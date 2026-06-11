"""confluence_html 파서 테스트 (api-spec.md 섹션 9).

픽스처: tests/fixtures/wiki_sample_v1.html (Confluence view 화면 구조 모사)
검증: 블록 매핑(heading/paragraph/table/table_row/notice), 계층 경로,
      doc_id 안정성, 제목 추출, 네비게이션 제외.
"""

from pathlib import Path

import pytest

from backend.services.parsers.confluence_html import parse_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parsed_v1():
    html = (FIXTURES / "wiki_sample_v1.html").read_text(encoding="utf-8")
    return parse_html(html, source_id="pageId:12345", url="http://wiki/page?pageId=12345")


def test_title_from_html_title_tag(parsed_v1):
    # "<페이지명> - <공간명> - Confluence" 에서 페이지명만 추출
    assert parsed_v1.title == "비대면 계좌 개설"


def test_doc_id_stable():
    """같은 source_id면 재파싱해도 doc_id 동일 — diff의 전제 조건."""
    html = (FIXTURES / "wiki_sample_v1.html").read_text(encoding="utf-8")
    a = parse_html(html, source_id="pageId:12345")
    b = parse_html(html, source_id="pageId:12345")
    assert a.doc_id == b.doc_id
    # 다른 source_id면 다른 doc_id
    c = parse_html(html, source_id="pageId:99999")
    assert a.doc_id != c.doc_id


def test_block_types_mapped(parsed_v1):
    types = {b.block_type for b in parsed_v1.blocks}
    assert "heading" in types
    assert "paragraph" in types
    assert "table" in types
    assert "table_row" in types
    assert "notice" in types


def test_nav_footer_excluded(parsed_v1):
    all_text = " ".join(b.text for b in parsed_v1.blocks)
    assert "네비게이션" not in all_text
    assert "푸터" not in all_text


def test_hierarchy_path(parsed_v1):
    """h2 아래 문단은 hierarchy_path에 해당 h2가 포함되어야 함 (h1은 제외)."""
    overview_paras = [
        b for b in parsed_v1.blocks
        if b.block_type == "paragraph" and "금융실명법" in b.text
    ]
    assert len(overview_paras) == 1
    hp = overview_paras[0].hierarchy_path
    assert hp is not None
    assert "1. 개요" in hp
    assert "비대면 계좌 개설" not in hp  # h1은 문서 제목급 — 경로 제외


def test_list_items_become_paragraphs(parsed_v1):
    texts = [b.text for b in parsed_v1.blocks if b.block_type == "paragraph"]
    assert any("영상통화 본인확인" in t for t in texts)


def test_table_rows_with_canonical(parsed_v1):
    rows = [b for b in parsed_v1.blocks if b.block_type == "table_row"]
    assert len(rows) == 2  # 데이터 행 2개 (헤더 제외)
    # canonical_text: "{주체}의 {맥락}는 {값}이다" 또는 "헤더: 값" 형태
    assert all(r.canonical_text for r in rows)
    assert any("당일 처리" in r.canonical_text for r in rows)


def test_notice_block(parsed_v1):
    notices = [b for b in parsed_v1.blocks if b.block_type == "notice"]
    assert len(notices) == 1
    assert "만 19세 미만" in notices[0].text
    # notice 내부 <p>가 paragraph로 중복 수집되지 않아야 함
    dup = [
        b for b in parsed_v1.blocks
        if b.block_type == "paragraph" and "만 19세 미만" in b.text
    ]
    assert not dup


def test_source_label_in_meta(parsed_v1):
    """ingest.build_metadata가 출처 표시에 쓰는 source_label 확인."""
    assert parsed_v1.meta["source_label"] == "비대면 계좌 개설"


def test_li_with_nested_p_no_duplication():
    """Confluence 특유의 <li><p>...</p></li> 구조에서 이중 수집 방지."""
    html = """
    <html><body><div id="main-content">
      <h2>절차</h2>
      <ul>
        <li><p>신분증 촬영 후 제출한다</p></li>
        <li>영상통화로 본인확인을 한다</li>
      </ul>
    </div></body></html>
    """
    parsed = parse_html(html, source_id="test:li-p")
    paras = [b.text for b in parsed.blocks if b.block_type == "paragraph"]
    # li가 p 내용을 포함해 1번만 수집 — p가 별도 블록으로 중복되면 안 됨
    assert paras.count("신분증 촬영 후 제출한다") == 1
    assert paras.count("영상통화로 본인확인을 한다") == 1
