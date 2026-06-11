"""Confluence/위키 HTML 파서 — HTML → ParsedDocument (api-spec.md 섹션 9).

위키 페이지 HTML(view 화면 또는 저장된 파일)을 기존 블록 스키마로 변환한다.
출력 스키마가 docling_pdf.py와 동일하므로 청킹(ingest.py)·검색(rag.py)을 그대로 공유.

블록 매핑:
  h1~h6                  → heading (h1=문서 제목급으로 hierarchy_path에서 제외)
  p, li, pre             → paragraph (같은 hierarchy_path 연속 블록은 청킹 시 병합)
  table                  → table (마크다운 전체) + table_row (행 단위 + canonical_text)
  Confluence 패널/매크로  → notice (info/note/warning/panel/aui-message)

이 모듈을 사용하는 곳:
  - scripts/sync_manual.py: 수집된 HTML을 파싱해 diff 인제스트에 전달
  - tests/test_confluence_parser.py: 픽스처 HTML 검증
"""

import hashlib
import logging
import re

from bs4 import BeautifulSoup, Tag

from ...models.parsed_document import Block, ParsedDocument

logger = logging.getLogger(__name__)

# Confluence 본문 영역 후보 셀렉터 — 위에서부터 먼저 매칭되는 것 사용.
# view 화면(#main-content), storage/export(wiki-content), 일반 HTML(article/body) 순.
# (사내 위키 wiki.hanwhawm.com 실측: #main-content 존재 확인 — 2026-06-11)
_CONTENT_SELECTORS = ["#main-content", "div.wiki-content", "article", "body"]

# 본문에서 제거할 태그 (네비게이션·스크립트류)
_STRIP_TAGS = ["script", "style", "nav", "header", "footer", "aside", "form"]

# notice로 매핑할 Confluence 패널 클래스 (부분 일치)
_NOTICE_CLASS_RE = re.compile(
    r"(confluence-information-macro|aui-message|panel\b|alert\b)"
)

# 개조식 헤딩 패턴 (사내 위키 실측: h태그 없이 "가." / "ㄱ." 으로 구조 표현하는 페이지 존재)
# h1~h6(depth 1~6)와 충돌하지 않도록 depth 7/8로 그 아래에 중첩시킨다.
# 숫자(1., 1))와 라틴(a., b.)은 이 위키에서 목록 항목으로 쓰여 헤딩에서 제외.
_KOREAN_HEADING_PATTERNS = [
    (re.compile(r"^[가-힣][\.\)]\s"), 7),    # "가. ..." "나) ..."
    (re.compile(r"^[ㄱ-ㅎ][\.\)]\s"), 8),    # "ㄱ. ..." "ㄴ) ..."
]


def _detect_korean_heading(line: str) -> int | None:
    """개조식 번호 패턴으로 헤딩 depth 추정. 헤딩 아니면 None."""
    t = line.strip()
    for pat, depth in _KOREAN_HEADING_PATTERNS:
        if pat.match(t):
            return depth
    return None


def _split_p_by_br(el: Tag) -> list[str]:
    """<p> 내용을 <br> 기준으로 줄 단위 분리.

    사내 위키 실측: 한 <p>에 <br> 50개 이상으로 항목을 나열하는 구조가 흔함.
    줄 단위로 나눠야 개조식 헤딩 감지와 청킹이 의미 단위로 동작한다.
    """
    lines: list[str] = []
    current: list[str] = []
    for node in el.descendants:
        if isinstance(node, Tag) and node.name == "br":
            line = _clean_text("".join(current))
            if line:
                lines.append(line)
            current = []
        elif isinstance(node, str):
            current.append(node)
    last = _clean_text("".join(current))
    if last:
        lines.append(last)
    return lines


def _doc_id_from_source(source_id: str) -> str:
    """source_id(위키 pageId·파일 경로) 기반 안정적 doc_id.

    경로가 아닌 source_id를 해시 → 같은 페이지는 재수집해도 같은 doc_id.
    (docling_pdf._doc_id_from_path와 같은 규칙: sha1 16자리)
    """
    return hashlib.sha1(source_id.encode("utf-8")).hexdigest()[:16]


def _clean_text(s: str) -> str:
    """연속 공백/개행 정리."""
    return re.sub(r"\s+", " ", s).strip()


# ---------- 표 처리 ----------


def _table_to_markdown(table: Tag) -> tuple[str, list[str], list[list[str]]]:
    """<table> → (마크다운 문자열, headers, data_rows).

    헤더 규칙: <th> 행이 있으면 그 행, 없으면 첫 행을 헤더로 간주.
    """
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [
            _clean_text(td.get_text(" ", strip=True))
            for td in tr.find_all(["th", "td"])
        ]
        if any(cells):
            rows.append(cells)

    if not rows:
        return "", [], []

    headers = rows[0]
    data_rows = rows[1:]

    md_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for r in data_rows:
        md_lines.append("| " + " | ".join(r) + " |")
    return "\n".join(md_lines), headers, data_rows


def _build_row_canonical(
    headers: list[str],
    row_cells: list[str],
    heading_context: str | None,
) -> str | None:
    """표 행 → 검색용 자연어 문장.

    docling_pdf._build_canonical_text와 동일 규칙 (모듈 독립 위해 사본 유지 —
    docling_pdf는 import 시 docling 패키지를 요구하므로 직접 import하지 않음).
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
        ctx = re.sub(r"^[ㄱ-ㅎ가-힣\d]+[\.\)]\s*", "", heading_context)
        ctx = re.sub(r"[\(（].*?[\)）]", "", ctx).strip()
        if ctx:
            return f"{subject}의 {ctx}는 {value}이다."

    return ", ".join(f"{h}: {v}" for h, v in paired)


# ---------- heading stack (docling_pdf와 동일 규칙) ----------


def _update_stack(stack: list[tuple[int, str]], depth: int, text: str) -> None:
    while stack and stack[-1][0] >= depth:
        stack.pop()
    stack.append((depth, text))


def _hierarchy_path(stack: list[tuple[int, str]]) -> list[str] | None:
    path = [t for d, t in stack if d > 1]  # depth 1(문서 제목급) 제외
    return path or None


def _heading_context(stack: list[tuple[int, str]]) -> str | None:
    for d, t in reversed(stack):
        if d > 1:
            return t
    return None


# ---------- 본문 순회 ----------


def _find_content_root(soup: BeautifulSoup) -> Tag:
    for sel in _CONTENT_SELECTORS:
        node = soup.select_one(sel)
        if node is not None:
            return node
    return soup  # 최후 폴백: 문서 전체


def _is_notice(tag: Tag) -> bool:
    classes = " ".join(tag.get("class") or [])
    return bool(_NOTICE_CLASS_RE.search(classes))


def _collect_blocks(root: Tag) -> list[Block]:
    """본문 루트를 문서 순서로 순회하며 Block 리스트 생성."""
    blocks: list[Block] = []
    order = 0
    stack: list[tuple[int, str]] = []
    # notice/table 내부의 p, li가 중복 수집되지 않도록 처리된 요소를 기억
    consumed: set[int] = set()

    for el in root.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "table", "div"]
    ):
        if id(el) in consumed:
            continue
        # 이미 처리된 컨테이너(notice/table) 내부 요소는 스킵
        if any(id(parent) in consumed for parent in el.parents):
            continue

        name = el.name

        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = _clean_text(el.get_text(" ", strip=True))
            if not text:
                continue
            depth = int(name[1])
            _update_stack(stack, depth, text)
            blocks.append(Block(
                text=text,
                block_type="heading",
                page=None,
                order=order,
                heading_level=depth,
                hierarchy_path=_hierarchy_path(stack),
            ))
            order += 1

        elif name == "div":
            # div는 notice 패널일 때만 블록화 (일반 div는 컨테이너라 스킵)
            if not _is_notice(el):
                continue
            text = _clean_text(el.get_text(" ", strip=True))
            if not text:
                continue
            consumed.add(id(el))
            blocks.append(Block(
                text=text,
                block_type="notice",
                page=None,
                order=order,
                hierarchy_path=_hierarchy_path(stack),
            ))
            order += 1

        elif name == "table":
            # 1×1 표는 표가 아니라 강조 박스(법령 인용 등) — notice로 처리
            # (사내 위키 실측: 한 셀짜리 표에 법조문 목록을 담는 패턴 존재)
            cells = el.find_all(["th", "td"])
            if len(cells) == 1:
                consumed.add(id(el))
                text = _clean_text(cells[0].get_text(" ", strip=True))
                if text:
                    blocks.append(Block(
                        text=text,
                        block_type="notice",
                        page=None,
                        order=order,
                        hierarchy_path=_hierarchy_path(stack),
                    ))
                    order += 1
                continue

            md, headers, data_rows = _table_to_markdown(el)
            if not md:
                continue
            consumed.add(id(el))
            hierarchy = _hierarchy_path(stack)

            # table 블록: 전체 마크다운 (docling_pdf와 동일 구조)
            blocks.append(Block(
                text=md,
                block_type="table",
                page=None,
                order=order,
                hierarchy_path=hierarchy,
            ))
            order += 1

            # table_row 블록: 행 단위 + canonical_text
            ctx = _heading_context(stack)
            for row_cells in data_rows:
                row_text = " | ".join(c for c in row_cells if c)
                if not row_text.strip():
                    continue
                blocks.append(Block(
                    text=row_text,
                    block_type="table_row",
                    page=None,
                    order=order,
                    hierarchy_path=hierarchy,
                    canonical_text=_build_row_canonical(headers, row_cells, ctx),
                ))
                order += 1

        elif name in ("p", "li", "pre"):
            # Confluence는 <li><p>텍스트</p></li> 구조가 흔함 —
            # li가 p 내용까지 수집하므로 li 내부의 p/pre는 스킵 (이중 수집 방지)
            if name in ("p", "pre") and el.find_parent("li") is not None:
                continue
            # li 내부에 중첩 ul이 있으면 직속 텍스트만 (중복 방지)
            if name == "li":
                direct = "".join(
                    c if isinstance(c, str) else c.get_text(" ", strip=True)
                    for c in el.children
                    if isinstance(c, str) or (isinstance(c, Tag) and c.name not in ("ul", "ol"))
                )
                lines = [_clean_text(direct)]
            elif name == "p":
                # <br> 구분 줄 단위 분리 (사내 위키: 한 p에 br 수십 개 패턴)
                lines = _split_p_by_br(el)
            else:
                lines = [_clean_text(el.get_text(" ", strip=True))]

            for line in lines:
                if not line:
                    continue
                # 개조식 헤딩 감지 — "가." depth7, "ㄱ." depth8 (h태그 아래 중첩)
                k_depth = _detect_korean_heading(line)
                if k_depth is not None:
                    _update_stack(stack, k_depth, line)
                    blocks.append(Block(
                        text=line,
                        block_type="heading",
                        page=None,
                        order=order,
                        heading_level=k_depth,
                        hierarchy_path=_hierarchy_path(stack),
                    ))
                else:
                    blocks.append(Block(
                        text=line,
                        block_type="paragraph",
                        page=None,
                        order=order,
                        hierarchy_path=_hierarchy_path(stack),
                    ))
                order += 1

    return blocks


# ---------- 공개 API ----------


def parse_html(
    html: str,
    *,
    source_id: str,
    url: str | None = None,
    title: str | None = None,
    doc_type: str = "manual",
) -> ParsedDocument:
    """위키/Confluence HTML을 ParsedDocument로 변환.

    Args:
        html: 페이지 HTML 전문
        source_id: 커넥터가 부여한 안정적 ID (pageId, 파일 상대경로 등)
        url: 원본 페이지 URL (출처 표시용)
        title: 페이지 제목 (없으면 <title> → 첫 h1 순으로 추출)
    """
    soup = BeautifulSoup(html, "html.parser")

    # 제목 추출: 인자 > <title> > 첫 h1
    if not title:
        if soup.title and soup.title.string:
            # Confluence <title>은 "페이지명 - 공간명 - Confluence" 형태가 흔함
            title = _clean_text(soup.title.string).split(" - ")[0]
        else:
            h1 = soup.find("h1")
            title = _clean_text(h1.get_text(" ", strip=True)) if h1 else None

    root = _find_content_root(soup)
    for tag_name in _STRIP_TAGS:
        for t in root.find_all(tag_name):
            t.decompose()

    blocks = _collect_blocks(root)

    table_count = sum(1 for b in blocks if b.block_type == "table")
    logger.info(
        "HTML 파싱 완료: %s — %d 블록 (표 %d개)",
        title or source_id, len(blocks), table_count,
    )

    return ParsedDocument(
        doc_id=_doc_id_from_source(source_id),
        source_path=url or source_id,
        doc_type=doc_type,
        title=title,
        document_path=None,
        page_count=None,
        blocks=blocks,
        meta={
            "parser": "confluence_html",
            "doc_type": "html",
            "source_id": source_id,
            "table_count": table_count,
            # ingest.build_metadata가 출처 표시(source_document)에 사용
            "source_label": title or source_id,
        },
    )
