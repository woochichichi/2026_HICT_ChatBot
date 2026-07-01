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

    # 답변 생성(LLM) 제공자 (api-spec.md 섹션 4) — gemini | openai
    # 임베딩(검색 벡터)과 독립. openai로 두면 "임베딩=기존(로컬/gemini) 그대로, 답변 생성만
    # OpenAI"로 동작 → ChromaDB 재인제스트 불필요. embedder.make_llm()에서 분기.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")

    # OpenAI (백업 → LLM_PROVIDER=openai 시 답변 생성 담당)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    # 작문(RAG 답변·코칭) 용도라 최저가 모델이 기본. 필요 시 env로 상향.
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

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

    # 오답 제보(피드백) 저장소 (api-spec.md 섹션 11) — 폐쇄망 대비 로컬 SQLite.
    # backend/services/feedback_store.py 의 FeedbackStore 가 사용.
    FEEDBACK_DB_PATH: str = os.getenv(
        "FEEDBACK_DB_PATH",
        str(_PROJECT_ROOT / "data" / "feedback.db"),
    )

    # AI 코치 TTS (routers/tts.py) — 엔진 교체형. TTS_ENGINE으로 선택.
    #   "xtts"   : Coqui XTTS-v2 (무료 오픈소스·자체호스팅·완전 오프라인=폐쇄망, 자연스러운
    #              남성 음성/클로닝). CPU는 느림(GPU 권장). 실패 시 edge로 폴백.
    #   "openai" : gpt-4o-mini-tts (감정 instructions, 유효 OPENAI_API_KEY 필요, 유료)
    #   "edge"   : edge-tts (무료 신경망, 인터넷 필요, 감정 평탄)
    #   "auto"   : openai(키 있으면) → edge
    # 모든 엔진 실패 시 프론트가 브라우저 Web Speech(OS 로컬)로 폴백.
    # ⚠️ XTTS는 torch/torchaudio/transformers가 bge-m3와 충돌해 '같은 venv'에 동거 불가 +
    #    CPU는 느림 → 별도 격리 venv/컨테이너(가능하면 GPU)에서 TTS_ENGINE=xtts로 구동 권장.
    #    이 PC(통합 venv)는 auto=edge로 동작. (docs: requirements-xtts.txt / wiki 참조)
    TTS_ENGINE: str = os.getenv("TTS_ENGINE", "auto")

    # XTTS-v2 — 자체호스팅 신경망 TTS. 모델은 최초 1회 다운로드(~2GB, 인터넷). CPML(비상업) 라이선스.
    XTTS_MODEL: str = os.getenv("XTTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
    XTTS_SPEAKER: str = os.getenv("XTTS_SPEAKER", "Damien Black")  # 깊은 남성(없으면 첫 화자)
    XTTS_DEVICE: str = os.getenv("XTTS_DEVICE", "cpu")  # GPU 있으면 "cuda"

    # OpenAI TTS (TTS_ENGINE=openai)
    OPENAI_TTS_MODEL: str = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    OPENAI_TTS_VOICE: str = os.getenv("OPENAI_TTS_VOICE", "onyx")  # 깊은 남성 → 고령 남성 톤
    # edge-tts 폴백 음성 — 한국어 남성(Hyunsu, 자연스러움). 대안 ko-KR-InJoonNeural.
    TTS_VOICE: str = os.getenv("TTS_VOICE", "ko-KR-HyunsuMultilingualNeural")


settings = Settings()
