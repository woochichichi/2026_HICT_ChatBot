"""FastAPI 엔트리포인트.

실행 방법 (프로젝트 루트에서):
  uvicorn backend.main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import chat, training


def _setup_logging() -> None:
    """앱 시작 시 로깅 설정.

    - backend.services.rag: DEBUG — 검색 단계별 점수 출력
    - 외부 라이브러리(httpx, chromadb): WARNING — 노이즈 억제
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("backend.services.rag").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)


_setup_logging()

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


