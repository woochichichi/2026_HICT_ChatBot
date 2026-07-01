"""FastAPI 엔트리포인트.

실행 방법 (프로젝트 루트에서):
  uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat, training, feedback, tts  # feedback: 제보 API, tts: AI코치 음성

# 제품명: 한화투자증권 PoC 리포지셔닝(v14). Swagger 노출 타이틀.
app = FastAPI(title="한화투자증권 AI 상담 어시스턴트", version="0.2.0")

# 프론트엔드 연동 대비 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(training.router, prefix="/api/training", tags=["training"])
# 오답 제보 — /api/feedback (POST/GET), /api/feedback/{id}/resolve (api-spec.md 섹션 11)
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
# AI 코치 음성 — /api/tts (고객 시나리오 낭독, 신경망 TTS)
app.include_router(tts.router, prefix="/api", tags=["tts"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


