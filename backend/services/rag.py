"""RAG 파이프라인 — 검색 + 답변 생성 (api-spec.md 섹션 3).

검색 흐름 (api-spec.md 섹션 3, 순서 중요):
  1. [벡터] faq_titles 쿼리 → Max Pooling (유사 제목 중복 제거)
  2. [벡터] faq_contents 쿼리 → 가중 병합 (TITLE_WEIGHT : CONTENT_WEIGHT)
  3. [BM25] faq_contents 전체 코퍼스 대상 키워드 검색
  4. [RRF] 벡터 순위 + BM25 순위를 RRF로 병합 (HYBRID_ALPHA 비중)
  5. 상위 top_k건 → LLM 컨텍스트

BM25 인덱스는 RAGService 초기화 시 faq_contents에서 자동 빌드 (인메모리).
서버 재시작 시 자동 재빌드되므로 별도 관리 불필요.

이 모듈을 사용하는 곳:
  - routers/chat.py: SSE 스트리밍 챗봇 API (generate_answer_stream 호출)
  - 향후 scripts/weight_search.py: 가중치 그리드 서치
"""

import logging
import re
from typing import AsyncIterator

import chromadb
from rank_bm25 import BM25Okapi

from ..config import settings
from .embedder import LLMService

logger = logging.getLogger(__name__)

# ChromaDB 컬렉션명
TITLES_COLLECTION = "faq_titles"
CONTENTS_COLLECTION = "faq_contents"


def get_chroma_client() -> chromadb.ClientAPI:
    """ChromaDB PersistentClient 싱글턴."""
    return chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)


def init_collections(client: chromadb.ClientAPI | None = None):
    """faq_titles, faq_contents 컬렉션 생성/가져오기 (cosine metric)."""
    client = client or get_chroma_client()
    titles = client.get_or_create_collection(
        TITLES_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    contents = client.get_or_create_collection(
        CONTENTS_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    return titles, contents


class RAGService:
    """
    검색 흐름 (api-spec.md 섹션 3, 순서 중요):
    1. 사용자 질문으로 faq_titles 벡터 쿼리 → 상위 10건 + 점수
    2. titles 결과에서 _sim 접미사 제거 후 Max Pooling (동일 원본 ID → 최고 점수만)
    3. 같은 질문으로 faq_contents 벡터 쿼리 → 상위 10건 + 점수
    4. Title 점수와 Content 점수를 가중 병합 → 벡터 점수 산출
    5. 같은 질문으로 BM25 키워드 검색 → BM25 점수 산출
    6. 벡터 순위 + BM25 순위를 RRF로 병합 (HYBRID_ALPHA 비중)
    7. 상위 top_k건을 LLM 컨텍스트로 전달
    """

    def __init__(self, llm: LLMService, chroma_client: chromadb.ClientAPI | None = None):
        self.llm = llm
        self.chroma = chroma_client or get_chroma_client()
        self.titles_col, self.contents_col = init_collections(self.chroma)
        self.title_weight = settings.TITLE_WEIGHT
        self.content_weight = settings.CONTENT_WEIGHT
        self.hybrid_alpha = settings.HYBRID_ALPHA
        self.rrf_k = settings.RRF_K
        self.bm25_search_n = settings.BM25_SEARCH_N

        # BM25 인덱스 빌드 — faq_contents 전체 로드 후 인메모리 인덱스 생성
        # 서버 시작 시 1회 실행, 재시작 시 자동 재빌드 (52건 기준 < 5ms)
        self._bm25_index, self._bm25_ids = self._build_bm25_index()
        logger.info(
            "[RAG] BM25 인덱스 빌드 완료 — %d건 (alpha=%.1f, k=%d)",
            len(self._bm25_ids), self.hybrid_alpha, self.rrf_k,
        )

    async def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Hybrid Search: 벡터 검색 + BM25 키워드 검색 → RRF 병합.

        api-spec.md 섹션 3: Hybrid Search
        - 벡터 검색: _expand_query_for_embedding()으로 쿼리 확장 후 임베딩
        - BM25 검색: 원본 쿼리 그대로 사용 (키워드 매칭 본래 목적)
        - RRF 병합: HYBRID_ALPHA 비중으로 두 순위를 결합
        - confidence 산출: 벡터 점수(0~1) 그대로 사용 (RRF 점수는 스케일 다름)
        """
        top_k = top_k or settings.TOP_K
        logger.info("[RAG] 검색 시작 — query=%r  top_k=%d", query, top_k)

        # --- 벡터 검색 ---
        # 키워드성 짧은 쿼리는 임베딩 품질이 낮으므로 자연어 문장으로 확장
        embedding_query = self._expand_query_for_embedding(query)
        if embedding_query != query:
            logger.debug("[RAG] 쿼리 확장: %r → %r", query, embedding_query)
        query_emb = (await self.llm.embed([embedding_query]))[0]

        # 1. faq_titles 벡터 쿼리
        title_results = self.titles_col.query(
            query_embeddings=[query_emb],
            n_results=10,
            include=["documents", "metadatas", "distances"],
        )

        # 2. Max Pooling: _sim 접미사 제거 후 동일 원본 ID는 최고 점수만
        title_scores = self._max_pool_titles(
            title_results["ids"][0], title_results["distances"][0]
        )

        # 3. faq_contents 벡터 쿼리
        content_results = self.contents_col.query(
            query_embeddings=[query_emb],
            n_results=10,
            include=["documents", "metadatas", "distances"],
        )
        content_scores = {
            doc_id: self._distance_to_similarity(dist)
            for doc_id, dist in zip(
                content_results["ids"][0], content_results["distances"][0]
            )
        }

        # 4. 제목+내용 벡터 점수 가중 병합 → {doc_id: vector_score}
        all_vec_ids = set(title_scores.keys()) | set(content_scores.keys())
        vector_scores: dict[str, float] = {}
        for doc_id in all_vec_ids:
            t = title_scores.get(doc_id, 0.0)
            c = content_scores.get(doc_id, 0.0)
            vector_scores[doc_id] = self.title_weight * t + self.content_weight * c

        _vec_top = sorted(vector_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        logger.debug(
            "[RAG] 벡터 점수 상위3: %s",
            "  ".join(f"{_id}={_s:.3f}" for _id, _s in _vec_top),
        )

        # --- BM25 키워드 검색 ---
        # 원본 쿼리 그대로 사용 (expand 없이 — 고유명사/약어 매칭이 목적)
        bm25_scores = self._bm25_search(query)
        _bm25_top = sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        logger.debug(
            "[RAG] BM25 점수 상위3: %s  (매칭 %d건)",
            "  ".join(f"{_id}={_s:.3f}" for _id, _s in _bm25_top),
            len(bm25_scores),
        )

        # --- RRF 병합 ---
        # confidence 산출용 best_vector_score: 벡터 검색 상위 점수 (0~1 스케일 유지)
        best_vector_score = max(vector_scores.values()) if vector_scores else 0.0
        merged = self._rrf_merge(vector_scores, bm25_scores)
        merged.sort(key=lambda x: x["score"], reverse=True)
        logger.debug(
            "[RAG] RRF 병합 후 상위3: %s",
            "  ".join(f"{_r['id']}={_r['score']:.5f}" for _r in merged[:3]),
        )

        # 5. 상위 top_k건에 메타데이터 부착
        results = []
        for item in merged[:top_k]:
            doc_id = item["id"]
            doc = self.contents_col.get(ids=[doc_id], include=["documents", "metadatas"])
            title_doc = self.titles_col.get(ids=[doc_id], include=["documents"])

            content = doc["documents"][0] if doc["documents"] else ""
            meta = doc["metadatas"][0] if doc["metadatas"] else {}
            title = title_doc["documents"][0] if title_doc["documents"] else ""

            results.append({
                "id": doc_id,
                "title": title,
                "content": content,
                # confidence 계산은 벡터 점수(0~1)로 — RRF 점수는 스케일이 달라 기준 재사용 불가
                "score": vector_scores.get(doc_id, best_vector_score * 0.5),
                "rrf_score": item["score"],
                "source_document": meta.get("source_document", ""),
                "source_page": meta.get("source_page", ""),
                "category": meta.get("category", ""),
            })
        logger.info(
            "[RAG] 검색 완료 — %d건 반환  top_score=%.3f  confidence=%s",
            len(results),
            results[0]["score"] if results else 0.0,
            self._calc_confidence(results[0]["score"] if results else 0.0),
        )
        for i, r in enumerate(results, 1):
            logger.debug(
                "[RAG]  [%d] id=%s  vec=%.3f  rrf=%.5f  제목=%r",
                i, r["id"], r["score"], r["rrf_score"], r["title"][:40],
            )
        return results

    async def generate_answer(self, query: str, contexts: list[dict]) -> dict:
        """검색된 컨텍스트 기반 LLM 답변 생성 (비스트리밍)."""
        system_prompt = self._build_system_prompt(contexts)
        answer = await self.llm.generate([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ])
        top_score = contexts[0]["score"] if contexts else 0.0
        return {
            "answer": answer,
            "sources": self._build_sources(contexts),
            "confidence": self._calc_confidence(top_score),
        }

    async def generate_answer_stream(
        self, query: str, contexts: list[dict]
    ) -> tuple[dict, AsyncIterator[str]]:
        """검색된 컨텍스트 기반 LLM 답변 스트리밍 생성 (api-spec.md 섹션 1: SSE).

        Returns:
            (pre_stream_data, token_iterator)
            - pre_stream_data: sources + confidence (SSE 'sources' 이벤트로 먼저 전송)
            - token_iterator: LLM 토큰 스트림 (SSE 'token' 이벤트로 전송)

        사용처: routers/chat.py의 SSE 스트리밍 엔드포인트
        """
        # 시스템 프롬프트 빌드 — chat_system.txt 템플릿에 컨텍스트 삽입
        system_prompt = self._build_system_prompt(contexts)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        # sources와 confidence는 RAG 검색 완료 시점에 이미 확정
        # → SSE 첫 이벤트로 프론트에 선전송하여 체감 대기 시간 단축
        top_score = contexts[0]["score"] if contexts else 0.0
        pre_stream_data = {
            "sources": self._build_sources(contexts),
            "confidence": self._calc_confidence(top_score),
        }

        # LLM 스트리밍 — embedder.py의 generate_stream() 사용
        token_iter = self.llm.generate_stream(messages)
        return pre_stream_data, token_iter

    # --- Private helpers ---

    def _build_bm25_index(self) -> tuple["BM25Okapi", list[str]]:
        """faq_contents 전체 문서를 로드해 BM25 인덱스 빌드.

        서버 시작 시 RAGService.__init__에서 1회 호출.
        52건 기준 < 5ms, 재시작 시 자동 재빌드 (캐시 불필요).
        반환값: (BM25Okapi 인덱스, doc_id 리스트) — 순서 대응
        """
        all_docs = self.contents_col.get(include=["documents"])
        ids: list[str] = all_docs["ids"]
        documents: list[str] = all_docs["documents"] or []

        # 한국어 토크나이저: 공백+특수문자 분리, 빈 토큰 제거
        # PoC 수준 — 형태소 분석기(konlpy) 없이도 FAQ 문서에서 충분한 정확도
        tokenized = [self._tokenize_ko(doc) for doc in documents]
        index = BM25Okapi(tokenized)
        return index, ids

    def _bm25_search(self, query: str) -> dict[str, float]:
        """BM25 키워드 검색. 원본 쿼리 그대로 사용 (고유명사/약어 매칭 목적).

        반환값: {doc_id: bm25_score} — 점수 0인 문서는 포함하지 않음
        """
        if not self._bm25_ids:
            return {}
        query_tokens = self._tokenize_ko(query)
        scores = self._bm25_index.get_scores(query_tokens)
        # 상위 bm25_search_n건만 반환 (점수 0 제외)
        scored = [
            (self._bm25_ids[i], float(scores[i]))
            for i in range(len(self._bm25_ids))
            if scores[i] > 0
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return dict(scored[: self.bm25_search_n])

    def _rrf_merge(
        self,
        vector_scores: dict[str, float],
        bm25_scores: dict[str, float],
    ) -> list[dict]:
        """RRF(Reciprocal Rank Fusion)로 벡터 순위와 BM25 순위를 병합.

        api-spec.md 섹션 3: RRF 공식
          rrf(d) = HYBRID_ALPHA * 1/(k + rank_vec(d))
                 + (1 - HYBRID_ALPHA) * 1/(k + rank_bm25(d))

        한쪽에만 존재하는 문서는 반대쪽 rank를 (코퍼스 크기 + 1)로 처리 → 자연스러운 패널티.
        """
        k = self.rrf_k
        alpha = self.hybrid_alpha
        corpus_size = len(self._bm25_ids)
        fallback_rank = corpus_size + 1

        # 각 검색결과를 점수 내림차순 정렬 후 rank 딕셔너리 생성 (1-based)
        vec_rank: dict[str, int] = {
            doc_id: i + 1
            for i, (doc_id, _) in enumerate(
                sorted(vector_scores.items(), key=lambda x: x[1], reverse=True)
            )
        }
        bm25_rank: dict[str, int] = {
            doc_id: i + 1
            for i, (doc_id, _) in enumerate(
                sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)
            )
        }

        all_ids = set(vec_rank.keys()) | set(bm25_rank.keys())
        merged = []
        for doc_id in all_ids:
            rv = vec_rank.get(doc_id, fallback_rank)
            rb = bm25_rank.get(doc_id, fallback_rank)
            rrf_score = alpha * (1.0 / (k + rv)) + (1 - alpha) * (1.0 / (k + rb))
            merged.append({"id": doc_id, "score": rrf_score})
        return merged

    @staticmethod
    def _tokenize_ko(text: str) -> list[str]:
        """한국어 정규식 토크나이저.

        공백 및 특수문자 경계로 분리. 형태소 분석 없이 FAQ 도메인에서 충분.
        빈 토큰, 단일 특수문자 제거.
        """
        tokens = re.split(r"[\s\(\)\[\]{}<>「」『』【】\.,;:!?/\\|'\"]+", text.lower())
        return [t for t in tokens if len(t) > 1]

    @staticmethod
    def _expand_query_for_embedding(query: str) -> str:
        """키워드성 단발 쿼리를 임베딩 품질이 높은 자연어 문장으로 확장.

        "고객기본정보" 같은 단어 단독 입력은 임베딩 벡터에 의미 정보가 부족해
        similarity score가 낮게 나온다. 자연어 문장으로 변환하면 관련 청크를
        정상 검색할 수 있다.

        규칙:
          - 이미 질문 형태인 경우(질문 패턴 포함)는 그대로 반환
          - 공백이 없거나 20자 이하 단어/짧은 구 → "에 대해 알려주세요" 접미사 추가
        """
        stripped = query.strip()
        # 이미 자연어 질문인지 판단하는 한국어 패턴
        question_patterns = [
            "?", "？",
            "어떻게", "무엇", "뭐", "어떤",
            "알려", "설명", "있어", "있나", "있습니까",
            "인가", "는가", "인지", "해줘", "해주세요",
            "됩니까", "됩니다", "하나요", "인가요",
        ]
        is_question = any(p in stripped for p in question_patterns)
        if not is_question and len(stripped) <= 20:
            return f"{stripped}에 대해 알려주세요"
        return stripped

    @staticmethod
    def _max_pool_titles(ids: list[str], distances: list[float]) -> dict[str, float]:
        """_sim 접미사 제거 후 동일 원본 ID는 최고 유사도만 채택."""
        pooled: dict[str, float] = {}
        for doc_id, dist in zip(ids, distances):
            original_id = doc_id.split("_sim")[0]
            sim = RAGService._distance_to_similarity(dist)
            if original_id not in pooled or sim > pooled[original_id]:
                pooled[original_id] = sim
        return pooled

    @staticmethod
    def _distance_to_similarity(distance: float) -> float:
        """cosine distance → similarity. ChromaDB cosine: distance ∈ [0, 2]."""
        return max(0.0, 1.0 - distance)

    @staticmethod
    def _calc_confidence(top_score: float) -> str:
        """api-spec.md confidence 기준."""
        if top_score >= 0.85:
            return "high"
        if top_score >= 0.70:
            return "medium"
        return "low"

    @staticmethod
    def _build_sources(contexts: list[dict]) -> list[dict]:
        """출처 목록 생성. source_page가 URL(Wiki)이면 별도 url 필드로 분리.

        PDF:  { title: "편람.pdf p.23 제목", reference: "편람.pdf p.23", url: null }
        Wiki: { title: "페이지제목 > 섹션제목", reference: "페이지제목", url: "https://..." }
        프론트엔드는 url 필드가 있으면 하이퍼링크로 렌더링.
        """
        sources = []
        for ctx in contexts:
            sp = ctx["source_page"]
            is_url = sp.startswith("http://") or sp.startswith("https://")
            if is_url:
                title_str = f"{ctx['source_document']} {ctx['title']}".strip()
                reference = ctx["source_document"]
                url: str | None = sp
            else:
                title_str = f"{ctx['source_document']} {sp} {ctx['title']}".strip()
                reference = f"{ctx['source_document']} {sp}".strip()
                url = None
            sources.append({
                "title": title_str,
                "reference": reference,
                "url": url,
                "relevance_score": round(ctx["score"], 4),
            })
        return sources

    @staticmethod
    def _build_system_prompt(contexts: list[dict]) -> str:
        """chat_system.txt 프롬프트에 컨텍스트 삽입.

        질문은 별도 user 메시지로 전달되므로 시스템 프롬프트에는
        컨텍스트만 삽입한다. (api-spec.md 섹션 1 참조)
        """
        import os
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "prompts", "chat_system.txt"
        )
        with open(prompt_path, encoding="utf-8") as f:
            template = f.read()

        # 번호 매기기 — 프론트엔드 출처 표시와 매칭 ([1], [2], ...)
        # source_page가 URL(Wiki)이면 페이지 제목만 표시, PDF이면 "문서명 페이지번호" 표시
        context_text = ""
        for i, ctx in enumerate(contexts, 1):
            sp = ctx["source_page"]
            is_url = sp.startswith("http://") or sp.startswith("https://")
            if is_url:
                source_ref = ctx["source_document"]
            else:
                source_ref = f"{ctx['source_document']} {sp}".strip()
            context_text += (
                f"[{i}] {ctx['title']}\n"
                f"출처: {source_ref}\n"
                f"내용: {ctx['content']}\n\n"
            )

        return template.replace("{context}", context_text)
