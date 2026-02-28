"""RAG 파이프라인 — 검색 + 답변 생성."""


class RAGService:
    """
    검색 흐름:
    1. 사용자 질문으로 faq_titles 컬렉션 쿼리 → 상위 10건 + 점수
    2. 같은 질문으로 faq_contents 컬렉션 쿼리 → 상위 10건 + 점수
    3. 문서 ID 기준 점수 가중 병합 (제목 50% + 내용 50%)
    4. 상위 3~5건을 LLM 컨텍스트로 전달
    """

    def __init__(self, embedder, chroma_client):
        self.embedder = embedder
        self.chroma_client = chroma_client
        self.title_weight = 0.5
        self.content_weight = 0.5

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """제목+내용 컬렉션에서 검색 후 점수 병합."""
        # TODO: 구현
        raise NotImplementedError

    async def generate_answer(self, query: str, contexts: list[dict]) -> dict:
        """검색된 컨텍스트 기반 LLM 답변 생성."""
        # TODO: 구현
        raise NotImplementedError
