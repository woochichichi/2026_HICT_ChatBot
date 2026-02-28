"""챗봇 모드 API."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None


class Source(BaseModel):
    title: str
    reference: str
    relevance_score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    confidence: str  # high / medium / low


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # TODO: RAG 파이프라인 연동
    return ChatResponse(
        answer="아직 구현되지 않았습니다.",
        sources=[],
        confidence="low",
    )
