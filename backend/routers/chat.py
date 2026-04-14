"""챗봇 모드 API — SSE 스트리밍 (api-spec.md 섹션 1).

SSE 이벤트 순서:
  1. event: sources — RAG 검색 완료 직후, 출처 + confidence 선전송
  2. event: token  — LLM 답변 토큰 스트리밍
  3. event: done   — 완료 신호
  4. event: error  — 에러 발생 시 (정상 흐름에서는 발생하지 않음)

프론트엔드 연동:
  - frontend/src/api/chat.js 에서 fetch + ReadableStream으로 소비
  - frontend/src/components/chat/ChatScreen.jsx 에서 렌더링
"""

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.embedder import GeminiService
from ..services.rag import RAGService

logger = logging.getLogger(__name__)

router = APIRouter()


# --- 요청 스키마 (api-spec.md 섹션 1) ---

class ChatRequest(BaseModel):
    """챗봇 질문 요청. session_id는 향후 Multi-turn 확장용 예약 필드."""
    question: str
    session_id: str | None = None


# --- SSE 유틸 ---

def _sse_event(event: str, data: dict) -> str:
    """SSE 이벤트 문자열 생성. 한국어 보존을 위해 ensure_ascii=False."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# --- 엔드포인트 ---

@router.post("/chat")
async def chat(request: ChatRequest):
    """챗봇 SSE 스트리밍 API.

    흐름:
      1. RAGService.search()로 관련 문서 검색
      2. sources + confidence 선전송 (api-spec.md: 체감 대기 시간 단축)
      3. LLM 토큰 스트리밍
      4. done 이벤트로 종료
    """

    async def event_stream():
        try:
            # RAGService 생성 — GeminiService를 LLM으로 사용
            # embedder.py의 LLMService 추상화를 통해 모델 교체 가능
            rag = RAGService(llm=GeminiService())

            # 1. RAG 검색 — rag.py의 search()가 Max Pooling + 가중 병합 수행
            contexts = await rag.search(request.question)

            # 2. 스트리밍 준비 — sources/confidence 계산 + LLM 토큰 이터레이터
            pre_stream, token_iter = await rag.generate_answer_stream(
                request.question, contexts
            )

            # 3. sources 이벤트 선전송 (api-spec.md 섹션 1: SSE 스트림 형식)
            yield _sse_event("sources", pre_stream)

            # 4. LLM 토큰 스트리밍
            async for token in token_iter:
                yield _sse_event("token", {"text": token})

            # 5. 완료
            yield _sse_event("done", {})

        except Exception as e:
            # 에러 시 클라이언트에 알림 — 프론트에서 onError 콜백으로 처리
            logger.exception("챗봇 SSE 에러: %s", e)
            yield _sse_event("error", {"message": str(e)})

    # StreamingResponse — FastAPI 내장, 추가 패키지 불필요
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",       # SSE 캐싱 방지
            "X-Accel-Buffering": "no",         # nginx/proxy 버퍼링 방지
        },
    )
