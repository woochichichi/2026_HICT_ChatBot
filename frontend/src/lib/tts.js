/**
 * TTS(음성 합성) 유틸 — AI 코치 시나리오 낭독.
 *
 * 2단계 전략:
 *   1) 서버 신경망 TTS: POST /api/tts (edge-tts, 한국어 '남성·고령' 음성) → mp3 재생. 고품질.
 *   2) 폴백: 브라우저 Web Speech(OS 로컬 음성). 서버/네트워크 실패 시 — 완전 오프라인 보장.
 *
 * 폐쇄망: 서버 TTS는 사내 온프레미스 신경망 TTS로 교체 가능(백엔드만), 안 되면 OS 로컬 음성 폴백.
 * 연관: backend/routers/tts.py, components/training/TrainingScreen.jsx
 */

let _audio = null; // 현재 재생 중인 서버 오디오
let _webVoices = [];

export function ttsSupported() {
  // 서버 TTS 또는 브라우저 음성 중 하나라도 가능하면 true
  return true;
}

/* ---------- 서버 신경망 TTS ---------- */
async function serverSpeak(text, { persona = "standard", onstart, onend }) {
  const res = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, persona }),
  });
  if (!res.ok) throw new Error("server tts failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  _audio = new Audio(url);
  _audio.onended = () => {
    URL.revokeObjectURL(url);
    _audio = null;
    onend && onend();
  };
  _audio.onerror = () => {
    URL.revokeObjectURL(url);
    _audio = null;
    onend && onend();
  };
  onstart && onstart();
  await _audio.play(); // 사용자 클릭(새 시나리오/🔊)에서 호출되므로 자동재생 허용
}

/* ---------- 브라우저 Web Speech 폴백 ---------- */
function webSupported() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}
function loadWebVoices() {
  return new Promise((resolve) => {
    if (!webSupported()) return resolve([]);
    const now = window.speechSynthesis.getVoices();
    if (now && now.length) {
      _webVoices = now;
      return resolve(now);
    }
    const onChange = () => {
      _webVoices = window.speechSynthesis.getVoices();
      resolve(_webVoices);
    };
    try {
      window.speechSynthesis.addEventListener("voiceschanged", onChange, { once: true });
    } catch {
      window.speechSynthesis.onvoiceschanged = onChange;
    }
    setTimeout(() => resolve(window.speechSynthesis.getVoices() || []), 600);
  });
}
function pickKoreanMaleVoice(voices) {
  if (!voices || !voices.length) return null;
  const ko = voices.filter((v) => /ko[-_]?KR/i.test(v.lang || "") || /korean|한국/i.test(v.name || ""));
  // 가능하면 남성 음성 우선(InJoon/male), 없으면 한국어 아무거나
  return (
    ko.find((v) => /injoon|male|남/i.test(v.name || "")) ||
    ko[0] ||
    null
  );
}
async function webSpeak(text, { rate = 0.95, pitch = 0.9, onstart, onend }) {
  if (!webSupported()) {
    onend && onend();
    return;
  }
  window.speechSynthesis.cancel();
  const voices = _webVoices.length ? _webVoices : await loadWebVoices();
  const u = new SpeechSynthesisUtterance(text);
  const v = pickKoreanMaleVoice(voices);
  if (v) u.voice = v;
  u.lang = (v && v.lang) || "ko-KR";
  u.rate = rate;
  u.pitch = pitch; // 낮게 → 나이 든 남성 느낌(폴백)
  if (onstart) u.onstart = onstart;
  if (onend) {
    u.onend = onend;
    u.onerror = onend;
  }
  window.speechSynthesis.speak(u);
}

/* ---------- 공개 API ---------- */
/**
 * 낭독. 서버 신경망 TTS 우선, 실패 시 브라우저 음성.
 * opts: { persona, rate, pitch, onstart, onend } (rate/pitch는 폴백용 숫자)
 */
export async function speak(text, opts = {}) {
  if (!text) return;
  cancelSpeak();
  try {
    await serverSpeak(text, opts);
  } catch {
    await webSpeak(text, opts);
  }
}

export function cancelSpeak() {
  if (_audio) {
    try {
      _audio.pause();
    } catch {
      /* noop */
    }
    _audio = null;
  }
  if (webSupported()) window.speechSynthesis.cancel();
}
