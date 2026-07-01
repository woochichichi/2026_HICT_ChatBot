"""LLM 서비스 추상화 — 모델 전환 대비 (api-spec.md 섹션 4)."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

from ..config import settings

logger = logging.getLogger(__name__)


async def _with_retry(fn, *, what: str, retries: int = 4, base_delay: float = 5.0):
    """일시적 오류(429 한도, 503 과부하)만 지수 백오프 재시도.

    검색·답변 생성 중 Gemini의 순간 과부하(503)나 분당 한도(429)로
    파이프라인이 통째 죽는 것을 방지 (api-spec.md 섹션 4). 그 외 오류는 즉시 전파.
    """
    delay = base_delay
    for attempt in range(retries + 1):
        try:
            return await asyncio.to_thread(fn)
        except Exception as e:
            msg = str(e)
            transient = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "UNAVAILABLE" in msg
            if not transient or attempt == retries:
                raise
            logger.warning("%s 일시 오류 — %.0f초 후 재시도 (%d/%d)", what, delay, attempt + 1, retries)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


class LLMService(ABC):
    """LLM 전환 대비 추상 인터페이스. 모든 구현체는 4개 메서드를 구현."""

    @abstractmethod
    async def generate(
        self,
        messages: list,
        temperature: float = 0.1,
        response_format: dict | None = None,
    ) -> str:
        """메시지 기반 텍스트 생성."""
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: list,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        """메시지 기반 텍스트 스트리밍 생성. SSE 응답용."""
        ...
        yield ""  # noqa: make it an async generator

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 배치를 벡터로 변환."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 계산."""
        ...


class GeminiService(LLMService):
    """Google AI Studio (Gemini) 구현체. google-genai SDK 사용."""

    def __init__(self) -> None:
        from google import genai

        self._client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self._chat_model = settings.GOOGLE_CHAT_MODEL
        self._embedding_model = settings.GOOGLE_EMBEDDING_MODEL

    @staticmethod
    def _messages_to_gemini(messages: list) -> tuple[str | None, list[dict]]:
        """OpenAI 형식 messages → Gemini (system, contents) 변환."""
        system = None
        contents = []
        for msg in messages:
            role = msg["role"]
            text = msg["content"]
            if role == "system":
                system = text
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": text}]})
            else:
                contents.append({"role": "user", "parts": [{"text": text}]})
        return system, contents

    async def generate(
        self,
        messages: list,
        temperature: float = 0.1,
        response_format: dict | None = None,
    ) -> str:
        from google.genai import types

        system, contents = self._messages_to_gemini(messages)
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system,
        )
        if response_format and response_format.get("type") == "json_object":
            config.response_mime_type = "application/json"

        resp = await _with_retry(
            lambda: self._client.models.generate_content(
                model=self._chat_model,
                contents=contents,
                config=config,
            ),
            what="답변 생성",
        )
        return resp.text or ""

    async def generate_stream(
        self,
        messages: list,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        from google.genai import types

        system, contents = self._messages_to_gemini(messages)
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system,
        )

        stream = self._client.models.generate_content_stream(
            model=self._chat_model,
            contents=contents,
            config=config,
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await _with_retry(
            lambda: self._client.models.embed_content(
                model=self._embedding_model,
                contents=texts,
            ),
            what="임베딩",
        )
        return [e.values for e in resp.embeddings]

    def count_tokens(self, text: str) -> int:
        resp = self._client.models.count_tokens(
            model=self._chat_model, contents=text
        )
        return resp.total_tokens


class LocalEmbeddingService(LLMService):
    """로컬 임베딩(sentence-transformers) + Gemini 생성 하이브리드 (api-spec.md 섹션 4).

    임베딩만 로컬 모델로 → 무제한·무료·오프라인(폐쇄망 실도입 정답, Gemini 일일 한도 회피).
    답변 생성은 임베딩과 별도 쿼터인 Gemini에 위임 (생성 한도는 넉넉).

    모델은 클래스 레벨에 1회 로드(캐시)되어 프로세스 내 재사용.
    """

    _model = None  # 클래스 캐시 — 모델 1회 로드

    def __init__(self) -> None:
        # 생성을 OpenAI가 맡으면(LLM_PROVIDER=openai) 이 Gemini는 안 쓰이므로 지연 생성.
        # 즉시 생성하면 google-genai SDK·GOOGLE_API_KEY를 강제해 "OpenAI 키 하나로
        # 작동"이 깨짐. 실제 Gemini 생성이 필요할 때만 만든다.
        self._gemini: GeminiService | None = None
        self._model_name = settings.LOCAL_EMBEDDING_MODEL

    def _get_gemini(self) -> "GeminiService":
        if self._gemini is None:
            self._gemini = GeminiService()
        return self._gemini

    def _get_model(self):
        if LocalEmbeddingService._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("로컬 임베딩 모델 로드 중: %s (최초 1회)", self._model_name)
            LocalEmbeddingService._model = SentenceTransformer(self._model_name)
        return LocalEmbeddingService._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        # encode는 CPU 바운드 → to_thread로 이벤트루프 블로킹 방지.
        # normalize=True → ChromaDB cosine 공간과 정합 (bge-m3 권장)
        vectors = await asyncio.to_thread(
            lambda: model.encode(
                texts, normalize_embeddings=True, batch_size=16,
                show_progress_bar=False,
            )
        )
        return [v.tolist() for v in vectors]

    async def generate(
        self,
        messages: list,
        temperature: float = 0.1,
        response_format: dict | None = None,
    ) -> str:
        return await self._get_gemini().generate(messages, temperature, response_format)

    async def generate_stream(
        self,
        messages: list,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        async for tok in self._get_gemini().generate_stream(messages, temperature):
            yield tok

    def count_tokens(self, text: str) -> int:
        # 인제스트는 별도 휴리스틱을 쓰므로 근사값으로 충분
        return max(1, len(text) // 2)


def make_llm() -> LLMService:
    """설정에 따라 임베딩·생성 제공자 선택 (api-spec.md 섹션 4).

    임베딩(검색 벡터)과 답변 생성(LLM)을 독립적으로 고름:
      - 임베딩: EMBEDDING_PROVIDER=local → 로컬(bge-m3), 그 외 → Gemini
      - 생성  : LLM_PROVIDER=openai → OpenAI(gpt-4o-mini 등), 그 외 → Gemini

    LLM_PROVIDER=openai 면 임베딩 경로는 건드리지 않고 generate/generate_stream만
    OpenAI로 위임 → ChromaDB 재인제스트 불필요. (LocalEmbeddingService가 임베딩 로컬 +
    생성 Gemini였던 것과 같은 하이브리드 패턴의 일반화)

    이 팩토리를 사용하는 곳: scripts/sync_manual.py, scripts/test_accuracy.py,
    routers/chat.py — 한 곳에서 제공자를 갈아끼우기 위함.
    """
    # 1) 임베딩 담당 서비스 선택 (검색 벡터 — 기존 동작 불변)
    embedder: LLMService
    if settings.EMBEDDING_PROVIDER.lower() == "local":
        embedder = LocalEmbeddingService()
    else:
        embedder = GeminiService()

    # 2) 생성(LLM)만 OpenAI로 교체 — 임베딩은 위 서비스 그대로 유지
    if settings.LLM_PROVIDER.lower() == "openai":
        return OpenAIChatWrapper(embedder)
    return embedder


class OpenAIChatWrapper(LLMService):
    """임베딩은 위임 서비스(로컬/Gemini) 그대로, 답변 생성만 OpenAI로 처리.

    "지금 Gemini가 하던 답변 생성만 OpenAI로 교체" 요구에 대응 (api-spec.md 섹션 4).
    검색 벡터는 base가 만든 것을 그대로 써 ChromaDB 재인제스트가 필요 없음.
    make_llm()이 LLM_PROVIDER=openai 일 때 생성.
    """

    def __init__(self, base: LLMService) -> None:
        self._base = base          # 임베딩 담당 (LocalEmbeddingService | GeminiService)
        self._openai = OpenAIService()  # 생성(gpt-4o-mini 등) 담당

    async def generate(
        self,
        messages: list,
        temperature: float = 0.1,
        response_format: dict | None = None,
    ) -> str:
        return await self._openai.generate(messages, temperature, response_format)

    async def generate_stream(
        self,
        messages: list,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        async for tok in self._openai.generate_stream(messages, temperature):
            yield tok

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # 검색 벡터는 base(로컬/Gemini)로 — 차원·스케일 유지 (재인제스트 불필요)
        return await self._base.embed(texts)

    def count_tokens(self, text: str) -> int:
        return self._base.count_tokens(text)


class OpenAIService(LLMService):
    """OpenAI 구현체. (백업용 보관)"""

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        # 빈 키로 조용히 동작하다 호출 시점에 모호한 401이 나는 걸 방지 —
        # LLM_PROVIDER=openai 인데 키 미설정이면 기동/팩토리 시점에 바로 알림.
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY가 비어 있습니다. .env에 키를 넣거나 LLM_PROVIDER를 gemini로 두세요."
            )
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.chat_model = settings.OPENAI_CHAT_MODEL
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL

    async def generate(
        self,
        messages: list,
        temperature: float = 0.1,
        response_format: dict | None = None,
    ) -> str:
        kwargs: dict = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = await self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    async def generate_stream(
        self,
        messages: list,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.chat_model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in resp.data]

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model(self.chat_model)
            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4
