"""TTS API — AI 코치 시나리오 음성 합성. 엔진 교체형(config.TTS_ENGINE).

엔진:
  - xtts   : Coqui XTTS-v2(무료·오픈소스·완전 오프라인=폐쇄망, 자연스러운 남성/클로닝).
             ⚠️ torch/torchaudio/transformers가 bge-m3와 충돌 → '별도 격리 venv/컨테이너'에서만
             구동(가능하면 GPU). 본 통합 venv에선 import 실패 → edge로 자동 폴백.
             설치: requirements-xtts.txt 참조.
  - openai : gpt-4o-mini-tts(감정/페르소나 instructions, 유효 OPENAI_API_KEY 필요, 유료).
  - edge   : edge-tts(무료 신경망, 인터넷 필요, 남성 Hyunsu). 본 PC 기본 동작 엔진.
실패 시 프론트(lib/tts.js)가 브라우저 Web Speech(OS 로컬)로 최종 폴백.

연관: backend/config.py(TTS_ENGINE/XTTS_*/OPENAI_TTS_*/TTS_VOICE), frontend/src/lib/tts.js
"""

import asyncio
import logging
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# 페르소나별 감정 연기 지시(OpenAI gpt-4o-mini-tts). 기본 '나이 든 남성'.
PERSONA_INSTRUCTIONS = {
    "standard": "차분하고 정중한 60대 한국 남성 고객. 자연스러운 일상 대화 톤으로 말한다.",
    "angry": "화가 많이 난 60대 한국 남성 고객. 짜증과 항의가 섞여 격앙되고 언성을 높여 따지듯 말한다.",
    "impatient": "매우 급하고 조급한 한국 남성 고객. 빠르고 퉁명스럽게, 결론을 재촉하듯 말한다.",
    "elderly": "70대 고령 한국 남성 고객. 느리고 어눌하게, 잘 못 알아들어 되묻는 듯 조심스럽게 말한다.",
    "anxious": "불안하고 걱정이 가득한 한국 남성 고객. 떨리고 초조하며 조심스러운 톤으로 말한다.",
    "demanding": "막무가내로 요구하는 한국 남성 고객. 강압적이고 단호하게 밀어붙이듯 말한다.",
    "talkative": "말이 많고 장황한 한국 남성 고객. 친근하지만 두서없이 늘어지게 말한다.",
    "skeptical": "의심이 많고 따지는 한국 남성 고객. 미심쩍어하며 꼬치꼬치 캐묻는 톤으로 말한다.",
}

# edge-tts 폴백용 (rate, pitch) — 자연스러움 우선, 소폭만 조정.
PERSONA_PROSODY = {
    "standard": ("-2%", "-3Hz"),
    "angry": ("+9%", "-4Hz"),
    "impatient": ("+16%", "+0Hz"),
    "elderly": ("-15%", "-5Hz"),
    "anxious": ("-3%", "+2Hz"),
    "demanding": ("+6%", "-4Hz"),
    "talkative": ("-3%", "+0Hz"),
    "skeptical": ("-2%", "-2Hz"),
}


class TtsRequest(BaseModel):
    text: str
    persona: str = "standard"


# ---------------- XTTS-v2 (자체호스팅) ----------------
_xtts_model = None
_xtts_lock = threading.Lock()


def _xtts_sync(text: str, persona: str) -> bytes:
    """XTTS-v2 합성(WAV bytes). 모델은 최초 1회 로드(다운로드 ~2GB). 별도 격리 venv 필요."""
    global _xtts_model
    import io
    import os

    import numpy as np
    import soundfile as sf

    if _xtts_model is None:
        with _xtts_lock:
            if _xtts_model is None:
                os.environ.setdefault("COQUI_TOS_AGREED", "1")  # CPML 비상업 동의(PoC)
                from TTS.api import TTS  # 격리 venv에서만 import 성공

                _xtts_model = TTS(settings.XTTS_MODEL).to(settings.XTTS_DEVICE)

    speaker = settings.XTTS_SPEAKER
    avail = getattr(_xtts_model, "speakers", None) or []
    if avail and speaker not in avail:
        speaker = avail[0]
    wav = _xtts_model.tts(text=text, speaker=speaker, language="ko")
    buf = io.BytesIO()
    sf.write(buf, np.array(wav), 24000, format="WAV")
    return buf.getvalue()


async def _xtts_tts(text: str, persona: str) -> tuple[bytes, str]:
    audio = await asyncio.to_thread(_xtts_sync, text, persona)
    return audio, "audio/wav"


# ---------------- OpenAI gpt-4o-mini-tts ----------------
def _openai_ready() -> bool:
    return (settings.OPENAI_API_KEY or "").strip().startswith("sk-")


async def _openai_tts(text: str, persona: str) -> tuple[bytes, str]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    instructions = PERSONA_INSTRUCTIONS.get(persona, PERSONA_INSTRUCTIONS["standard"])
    data = bytearray()
    async with client.audio.speech.with_streaming_response.create(
        model=settings.OPENAI_TTS_MODEL,
        voice=settings.OPENAI_TTS_VOICE,
        input=text,
        instructions=instructions,
        response_format="mp3",
    ) as resp:
        async for chunk in resp.iter_bytes():
            data += chunk
    return bytes(data), "audio/mpeg"


# ---------------- edge-tts (기본 폴백) ----------------
async def _edge_tts(text: str, persona: str) -> tuple[bytes, str]:
    import edge_tts

    rate, pitch = PERSONA_PROSODY.get(persona, PERSONA_PROSODY["standard"])
    comm = edge_tts.Communicate(text, settings.TTS_VOICE, rate=rate, pitch=pitch)
    data = bytearray()
    async for chunk in comm.stream():
        if chunk.get("type") == "audio":
            data += chunk["data"]
    return bytes(data), "audio/mpeg"


def _engine_order() -> list[str]:
    """TTS_ENGINE 설정 → 시도 순서(항상 edge로 폴백)."""
    eng = (settings.TTS_ENGINE or "auto").lower()
    if eng == "xtts":
        return ["xtts", "edge"]
    if eng == "openai":
        return ["openai", "edge"]
    if eng == "edge":
        return ["edge"]
    # auto
    return (["openai"] if _openai_ready() else []) + ["edge"]


_ENGINES = {"xtts": _xtts_tts, "openai": _openai_tts, "edge": _edge_tts}


@router.post("/tts")
async def synthesize(req: TtsRequest):
    """텍스트 → 음성. 설정 엔진 우선, 실패 시 edge로 폴백."""
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text가 비어 있습니다.")

    for name in _engine_order():
        try:
            audio, mime = await _ENGINES[name](text, req.persona)
            if audio:
                return Response(
                    content=audio,
                    media_type=mime,
                    headers={"Cache-Control": "no-store", "X-TTS-Engine": name},
                )
        except Exception as e:
            logger.warning("TTS 엔진 '%s' 실패: %s", name, e)

    # 전 엔진 실패 → 프론트가 브라우저 음성으로 폴백
    raise HTTPException(status_code=503, detail="음성 합성 실패(브라우저 음성으로 대체).")
