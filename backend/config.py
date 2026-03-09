"""프로젝트 설정 관리."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """환경변수 기반 설정."""

    # Google AI Studio (기본)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_CHAT_MODEL: str = os.getenv("GOOGLE_CHAT_MODEL", "gemini-2.5-flash")
    GOOGLE_EMBEDDING_MODEL: str = os.getenv("GOOGLE_EMBEDDING_MODEL", "gemini-embedding-001")

    # OpenAI (백업)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")

    # RAG 검색 가중치 (api-spec.md 섹션 3)
    TITLE_WEIGHT: float = float(os.getenv("TITLE_WEIGHT", "0.5"))
    CONTENT_WEIGHT: float = float(os.getenv("CONTENT_WEIGHT", "0.5"))
    TOP_K: int = int(os.getenv("TOP_K", "5"))


settings = Settings()
