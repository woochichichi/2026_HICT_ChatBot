"""파싱된 문서의 최소 스키마 (POC). 다른 파서에서도 재사용."""

from pydantic import BaseModel


class Block(BaseModel):
    text: str
    block_type: str = "text"
    page: int | None = None
    order: int
    heading_level: int | None = None


class ParsedDocument(BaseModel):
    doc_id: str
    source_path: str
    title: str | None = None
    page_count: int | None = None
    blocks: list[Block]
    meta: dict
