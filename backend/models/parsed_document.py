"""VectorDB 적재용 공통 문서 스키마 (PoC).

업무편람, 공지, FAQ 등 문서 종류에 관계없이 동일한 구조로 파싱 결과를 표현한다.
다른 파서(docling, pymupdf 등)에서도 이 스키마로 변환하여 사용한다.
"""

from pydantic import BaseModel


class Block(BaseModel):
    """문서 내 단위 블록. block_type: heading | paragraph | rule | table | table_row"""

    text: str
    block_type: str = "paragraph"
    page: int | None = None
    order: int
    heading_level: int | None = None
    hierarchy_path: list[str] | None = None   # 문서 내부 소제목 경로
    canonical_text: str | None = None          # 검색 최적화용 평문


class ParsedDocument(BaseModel):
    """파싱된 문서 공통 스키마. doc_type: manual | notice | faq"""

    doc_id: str
    source_path: str
    doc_type: str = "manual"
    title: str | None = None
    document_path: list[str] | None = None    # 문서 상위 경로 (편람 목차 등)
    page_count: int | None = None
    blocks: list[Block]
    meta: dict
