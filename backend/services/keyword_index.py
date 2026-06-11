"""BM25 키워드 인덱스 — Hybrid Search의 키워드 축 (api-spec.md 섹션 10).

벡터 검색이 약한 고유명사·코드(예: "K-OTC", "80~89", "스마트 OTP")를
글자 단위 매칭으로 보완한다. rag.py의 RAGService.search()가 RRF 융합에 사용.

토크나이저: 영문/숫자는 단어 토큰 + 한국어는 문자 bigram.
  - kiwipiepy(형태소)를 시도했으나 비ASCII 경로(한글 사용자명)에서 네이티브 모델
    로딩 실패 + 인터프리터 종료 시 세그폴트 발생 → 의존성 제거
    (docs/TROUBLESHOOTING.md 2026-06-11 항목 참조)
  - bigram은 "고객번호는"(조사 포함) ↔ "고객번호" 질의를 자연스럽게 매칭시키고
    순수 파이썬이라 폐쇄망에서도 동작 보장

인덱스 원본: ChromaDB faq_titles + faq_contents 문서 텍스트 (제목+본문 결합).
신선도: 컬렉션 count가 바뀌면 다음 검색 때 자동 재구축 (401청크 기준 수십 ms).

이 모듈을 사용하는 곳:
  - backend/services/rag.py: HYBRID_ENABLED=true일 때 RRF 융합
  - tests/test_keyword_index.py: 토크나이저/검색 검증
"""

import logging
import re

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# 영문·숫자 토큰: "K-OTC", "80~89", "OTP" 같은 코드 보존 (하이픈·물결·점 허용)
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-~.]*")
# 한국어 연속 구간
_KOREAN_RE = re.compile(r"[가-힣]+")


def _korean_bigrams(run: str) -> list[str]:
    """한국어 구간 → 문자 bigram. 1글자는 그대로.

    예: "고객번호는" → ["고객", "객번", "번호", "호는"]
    질의 "고객번호" → ["고객", "객번", "번호"] — 조사가 붙어도 매칭됨.
    """
    if len(run) < 2:
        return [run]
    return [run[i : i + 2] for i in range(len(run) - 1)]


def tokenize(text: str) -> list[str]:
    """검색용 토큰화 — 영문/숫자 단어 + 한국어 bigram."""
    tokens = [t.lower() for t in _WORD_RE.findall(text)]
    for run in _KOREAN_RE.findall(text):
        tokens.extend(_korean_bigrams(run))
    return tokens


class KeywordIndex:
    """ChromaDB 컬렉션 위에 BM25 인덱스를 얹는 래퍼."""

    def __init__(self, titles_col, contents_col):
        self.titles_col = titles_col
        self.contents_col = contents_col
        self._bm25: BM25Okapi | None = None
        self._ids: list[str] = []
        self._indexed_count = -1  # 마지막 인덱싱 시점의 컬렉션 크기

    def _rebuild(self) -> None:
        """제목+본문 결합 텍스트로 BM25 재구축."""
        contents = self.contents_col.get(include=["documents"])
        titles = self.titles_col.get(include=["documents"])
        title_by_id = dict(zip(titles["ids"], titles["documents"]))

        self._ids = list(contents["ids"])
        corpus = [
            tokenize(f"{title_by_id.get(cid, '')}\n{doc or ''}")
            for cid, doc in zip(contents["ids"], contents["documents"])
        ]
        # BM25Okapi는 빈 코퍼스에서 ZeroDivisionError — 가드
        self._bm25 = BM25Okapi(corpus) if corpus else None
        self._indexed_count = len(self._ids)
        logger.info("BM25 인덱스 구축: %d 청크", len(self._ids))

    def _refresh_if_stale(self) -> None:
        """컬렉션 크기가 바뀌었으면 재구축 (증분 인제스트 후 자동 반영)."""
        current = self.contents_col.count()
        if current != self._indexed_count:
            self._rebuild()

    def search(self, query: str, top_n: int = 20) -> list[tuple[str, float]]:
        """BM25 검색 — [(chunk_id, score)] 점수 내림차순. 0점은 제외."""
        self._refresh_if_stale()
        if self._bm25 is None:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = self._bm25.get_scores(q_tokens)
        ranked = sorted(
            ((cid, float(s)) for cid, s in zip(self._ids, scores) if s > 0),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_n]
