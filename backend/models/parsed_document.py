"""파싱된 문서의 최소 스키마 (POC). 다른 파서에서도 재사용."""

from pydantic import BaseModel

# 문서 내용을 나눈 조각
class Block(BaseModel):
    text: str
    page: int | None = None
    # 문서 안에서 몇 번째 조각인지
    order: int


class ParsedDocument(BaseModel):
    doc_id: str
    source_path: str
    title: str | None = None
    page_count: int | None = None
    blocks: list[Block]
    meta: dict
