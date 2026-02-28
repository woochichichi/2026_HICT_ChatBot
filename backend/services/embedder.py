"""임베딩 서비스 — LLM 전환 대비 추상화."""

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """임베딩 서비스 인터페이스."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """텍스트를 벡터로 변환."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """텍스트 배치를 벡터 배치로 변환."""
        ...


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI 임베딩 구현체. PoC용."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        # TODO: OpenAI 클라이언트 초기화

    async def embed(self, text: str) -> list[float]:
        # TODO: 구현
        raise NotImplementedError

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # TODO: 구현
        raise NotImplementedError
