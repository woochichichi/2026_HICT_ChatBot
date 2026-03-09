"""LLM 서비스 추상화 — 모델 전환 대비 (api-spec.md 섹션 4)."""

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator

from ..config import settings


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

        resp = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._chat_model,
            contents=contents,
            config=config,
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
        resp = await asyncio.to_thread(
            self._client.models.embed_content,
            model=self._embedding_model,
            contents=texts,
        )
        return [e.values for e in resp.embeddings]

    def count_tokens(self, text: str) -> int:
        resp = self._client.models.count_tokens(
            model=self._chat_model, contents=text
        )
        return resp.total_tokens


class OpenAIService(LLMService):
    """OpenAI 구현체. (백업용 보관)"""

    def __init__(self) -> None:
        from openai import AsyncOpenAI

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
