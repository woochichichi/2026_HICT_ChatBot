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

    # LLM 프로바이더 전환 (gemini | openai) — Gemini 할당량 소진 시 openai로 교체
    # openai 사용 시 OPENAI_EMBEDDING_MODEL=text-embedding-3-large 권장 (3072차원, 재인제스트 불필요)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")

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

    # Hybrid Search 파라미터 (api-spec.md 섹션 3: Hybrid Search)
    # HYBRID_ALPHA: 벡터 검색 비중 (0.0=BM25 only, 1.0=vector only)
    # 기본값 0.7 — 의미 검색 위주이되 키워드 매칭을 30% 반영
    HYBRID_ALPHA: float = float(os.getenv("HYBRID_ALPHA", "0.7"))
    # RRF_K: Reciprocal Rank Fusion 상수. 표준값 60 (논문 Cormack et al. 2009)
    RRF_K: int = int(os.getenv("RRF_K", "60"))
    # BM25_SEARCH_N: BM25 후보 건수 (벡터 검색 n_results=10과 동일하게 맞춤)
    BM25_SEARCH_N: int = int(os.getenv("BM25_SEARCH_N", "10"))


settings = Settings()
