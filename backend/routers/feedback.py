"""오답 제보(피드백) API (api-spec.md 섹션 11).

엔드포인트:
  POST /api/feedback              — 제보 등록 (사유 필수)
  GET  /api/feedback?status=...   — 제보 목록 조회 (검토 화면용)
  POST /api/feedback/{id}/resolve — 처리완료 전환 (검토자)

라우터는 얇게(검증/직렬화), 저장은 services/feedback_store.py FeedbackStore.
프론트 연동: frontend/src/api/feedback.js, ChatScreen(제보 버튼/모달), ReviewScreen(검토).
"""

import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..services.feedback_store import FeedbackStore

logger = logging.getLogger(__name__)

router = APIRouter()


# --- 스키마 (api-spec.md 섹션 11) ---

class SourceItem(BaseModel):
    """제보 시점 출처 스냅샷 — ChatScreen 메시지의 sources[] 항목과 동일 형태."""
    title: str = ""
    url: str | None = None
    relevance_score: float = 0.0


class FeedbackRequest(BaseModel):
    question: str = ""
    answer: str = ""
    reason: str                       # 필수
    suggested: str | None = None      # 정답 제안(선택)
    sources: list[SourceItem] = []    # 답변 출처 스냅샷
    confidence: str | None = None     # high|medium|low 스냅샷


# --- 엔드포인트 ---

@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """오답 제보 등록. 사유(reason)는 필수."""
    if not req.reason.strip():
        raise HTTPException(status_code=400, detail="제보 사유를 입력하세요.")

    # sources는 JSON 문자열로 직렬화해 저장(스냅샷). 한국어 보존 ensure_ascii=False.
    sources_json = json.dumps(
        [s.model_dump() for s in req.sources], ensure_ascii=False
    )

    with FeedbackStore(settings.FEEDBACK_DB_PATH) as fb:
        fid = fb.submit(
            question=req.question,
            answer=req.answer,
            reason=req.reason.strip(),
            suggested=(req.suggested.strip() if req.suggested else None),
            sources_json=sources_json,
            confidence=req.confidence,
        )

    logger.info("오답 제보 등록: id=%s", fid)
    return {"id": fid, "status": "open"}


@router.get("/feedback")
async def list_feedback(status: str | None = None):
    """제보 목록 조회. status=open|resolved 로 필터(생략 시 전체)."""
    if status is not None and status not in ("open", "resolved"):
        raise HTTPException(status_code=400, detail="status는 open 또는 resolved만 허용됩니다.")

    with FeedbackStore(settings.FEEDBACK_DB_PATH) as fb:
        rows = fb.list(status)

    # sources_json 문자열을 파싱해 sources 배열로 펼쳐 반환(프론트 편의)
    items = []
    for r in rows:
        d = dict(r)
        try:
            d["sources"] = json.loads(d.get("sources_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["sources"] = []
        items.append(d)
    return {"items": items}


@router.post("/feedback/{feedback_id}/resolve")
async def resolve_feedback(feedback_id: int, note: str | None = None):
    """제보를 처리완료로 전환. 이미 처리/미존재면 404."""
    with FeedbackStore(settings.FEEDBACK_DB_PATH) as fb:
        ok = fb.resolve(feedback_id, note)
    if not ok:
        raise HTTPException(status_code=404, detail="이미 처리되었거나 존재하지 않는 제보입니다.")
    return {"id": feedback_id, "status": "resolved"}
