"""FastAPI 엔트리포인트.

실행 방법 (프로젝트 루트에서):
  uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat, training

app = FastAPI(title="증권 상담원 AI 코치", version="0.1.0")

# 프론트엔드 연동 대비 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(training.router, prefix="/api/training", tags=["training"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
