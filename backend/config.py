"""프로젝트 설정 관리."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트: config.py(backend/) → 상위 디렉토리
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 사내 SSL 인터셉트 환경(Zscaler 등 자체 서명 CA) 대응.
# google-genai SDK는 _api_client._ensure_httpx_ssl_ctx에서 SSL_CERT_FILE을 직접 인식.
# requests/urllib 호환을 위해 REQUESTS_CA_BUNDLE/CURL_CA_BUNDLE도 함께 동기화.
# docs/TROUBLESHOOTING.md 2026-05-08 항목 참조.
_ssl_cert_file = os.environ.get("SSL_CERT_FILE")
if _ssl_cert_file:
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _ssl_cert_file)
    os.environ.setdefault("CURL_CA_BUNDLE", _ssl_cert_file)


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

    CHROMA_DB_PATH: str = os.getenv(
        "CHROMA_DB_PATH",
        str(_PROJECT_ROOT / "data" / "chroma_db"),
    )
    DATA_DIR: str = os.getenv("DATA_DIR", str(_PROJECT_ROOT / "data"))

    # RAG 검색 가중치 (api-spec.md 섹션 3)
    TITLE_WEIGHT: float = float(os.getenv("TITLE_WEIGHT", "0.5"))
    CONTENT_WEIGHT: float = float(os.getenv("CONTENT_WEIGHT", "0.5"))
    TOP_K: int = int(os.getenv("TOP_K", "5"))


settings = Settings()
