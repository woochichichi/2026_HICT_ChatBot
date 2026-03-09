"""RAG 파이프라인 — 검색 + 답변 생성 (api-spec.md 섹션 3)."""

import chromadb

from ..config import settings
from .embedder import LLMService

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
    1. 사용자 질문으로 faq_titles 쿼리 → 상위 10건 + 점수
    2. titles 결과에서 _sim 접미사 제거 후 Max Pooling (동일 원본 ID → 최고 점수만)
    3. 같은 질문으로 faq_contents 쿼리 → 상위 10건 + 점수
    4. Title 점수와 Content 점수를 가중 병합
    5. 상위 top_k건을 LLM 컨텍스트로 전달
    """

    def __init__(self, llm: LLMService, chroma_client: chromadb.ClientAPI | None = None):
        self.llm = llm
        self.chroma = chroma_client or get_chroma_client()
        self.titles_col, self.contents_col = init_collections(self.chroma)
        self.title_weight = settings.TITLE_WEIGHT
        self.content_weight = settings.CONTENT_WEIGHT

    async def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """제목+내용 컬렉션에서 검색 후 점수 병합."""
        top_k = top_k or settings.TOP_K
        query_emb = (await self.llm.embed([query]))[0]

        # 1. faq_titles 쿼리
        title_results = self.titles_col.query(
            query_embeddings=[query_emb],
            n_results=10,
            include=["documents", "metadatas", "distances"],
        )

        # 2. Max Pooling: _sim 접미사 제거 후 동일 원본 ID는 최고 점수만
        title_scores = self._max_pool_titles(
            title_results["ids"][0], title_results["distances"][0]
        )

        # 3. faq_contents 쿼리
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

        # 4. 가중 병합
        all_ids = set(title_scores.keys()) | set(content_scores.keys())
        merged = []
        for doc_id in all_ids:
            t = title_scores.get(doc_id, 0.0)
            c = content_scores.get(doc_id, 0.0)
            merged.append({
                "id": doc_id,
                "score": self.title_weight * t + self.content_weight * c,
            })
        merged.sort(key=lambda x: x["score"], reverse=True)

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
                "score": item["score"],
                "source_document": meta.get("source_document", ""),
                "source_page": meta.get("source_page", ""),
                "category": meta.get("category", ""),
            })
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

    # --- Private helpers ---

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
        return [
            {
                "title": f"{ctx['source_document']} {ctx['source_page']} {ctx['title']}".strip(),
                "reference": f"{ctx['source_document']} {ctx['source_page']}",
                "relevance_score": round(ctx["score"], 4),
            }
            for ctx in contexts
        ]

    @staticmethod
    def _build_system_prompt(contexts: list[dict]) -> str:
        """chat_system.txt 프롬프트에 컨텍스트 삽입."""
        import os
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "prompts", "chat_system.txt"
        )
        with open(prompt_path, encoding="utf-8") as f:
            template = f.read()

        context_text = ""
        for i, ctx in enumerate(contexts, 1):
            context_text += (
                f"[{i}] {ctx['title']}\n"
                f"출처: {ctx['source_document']} {ctx['source_page']}\n"
                f"내용: {ctx['content']}\n\n"
            )

        return template.replace("{context}", context_text).replace("{question}", "")
