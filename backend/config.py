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

    # 임베딩 제공자 (api-spec.md 섹션 4) — gemini | local
    # local: sentence-transformers 로컬 모델(무제한·무료·오프라인, 폐쇄망 실도입).
    #        답변 생성은 그대로 Gemini(별도 쿼터) 위임.
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "gemini")
    LOCAL_EMBEDDING_MODEL: str = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-m3")

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

    # confidence 뱃지 임계값 (api-spec.md 섹션 1·3) — top 벡터 유사도 기준.
    # bge-m3(1024) 재보정값: 정답 1위 케이스 점수가 0.30~0.78에 분포(최댓값 0.78)해
    # 기존 Gemini 기준 0.85/0.70이면 high가 절대 안 뜨고 대부분 low로 깔림.
    # 측정(data/eval/accuracy_bge_m3_search_..., 30문항): 0.70↑ 9건 / 0.50~0.70 14건 / 0.50↓ 7건.
    # provider 교체 시(임베딩 점수 스케일이 달라짐) 이 값 재튜닝 필요 → 환경변수로 분리.
    CONFIDENCE_HIGH_THRESHOLD: float = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", "0.70"))
    CONFIDENCE_MEDIUM_THRESHOLD: float = float(os.getenv("CONFIDENCE_MEDIUM_THRESHOLD", "0.50"))

    # 페이지당 top_k 청크 캡 (api-spec.md 섹션 3: 답변 품질) — 같은 위키 페이지의
    # 여러 청크가 top_k를 독식(예: 배당옵션 FAQ 4청크)하는 것 방지. 출처 도배 해소 +
    # LLM 컨텍스트 다양성↑. 1이면 페이지당 최고 점수 1청크만 → 출처가 페이지 단위로 유일.
    # citation [n]이 컨텍스트 순번과 1:1이므로, 캡>1이면 출처 목록에 동일 페이지가
    # 다시 보일 수 있음(번호 정합은 유지). 기본 1.
    PER_PAGE_CHUNK_CAP: int = int(os.getenv("PER_PAGE_CHUNK_CAP", "1"))

    # 검색 쿼리 동의어 확장 (api-spec.md 섹션 3) — "미국 주식"→"해외주식" 등
    # 명시적 false로 끌 수 있음(정확도 A/B 테스트용). 기본 on.
    QUERY_EXPANSION_ENABLED: bool = os.getenv("QUERY_EXPANSION_ENABLED", "true").lower() == "true"

    # Hybrid Search (api-spec.md 섹션 10) — BM25 키워드 + 벡터 RRF 융합
    HYBRID_ENABLED: bool = os.getenv("HYBRID_ENABLED", "true").lower() == "true"
    RRF_K: int = int(os.getenv("RRF_K", "60"))            # RRF 평탄화 상수 (표준값 60)
    KEYWORD_TOP_N: int = int(os.getenv("KEYWORD_TOP_N", "20"))  # BM25 후보 수

    # 위키 수집 + 증분 동기화 (api-spec.md 섹션 9)
    # scripts/sync_manual.py --source crawl 에서 사용
    WIKI_BASE_URL: str = os.getenv("WIKI_BASE_URL", "")          # 예: https://wiki.hanwhawm.com (루트 — viewpage가 루트 경로)
    WIKI_COOKIE: str = os.getenv("WIKI_COOKIE", "")              # 브라우저에서 복사한 세션 쿠키
    WIKI_SPACE_KEYS: str = os.getenv("WIKI_SPACE_KEYS", "")      # 쉼표 구분, 예: BM001,BM002
    # URL 템플릿 — 사이트마다 경로가 달라 설정으로 주입 ({base}, {space} 치환)
    # 실측(2026-06-11): 목록 화면은 /collector/ 하위, 본문(viewpage)은 루트 하위
    WIKI_PAGE_LIST_URL: str = os.getenv(
        "WIKI_PAGE_LIST_URL", "{base}/collector/pages.action?key={space}",
    )
    WIKI_RECENT_URL: str = os.getenv(
        "WIKI_RECENT_URL", "{base}/pages/recentlyupdated.action?key={space}",
    )
    WIKI_CRAWL_DELAY: float = float(os.getenv("WIKI_CRAWL_DELAY", "0.5"))
    META_DB_PATH: str = os.getenv(
        "META_DB_PATH",
        str(_PROJECT_ROOT / "data" / "meta.db"),
    )


settings = Settings()
