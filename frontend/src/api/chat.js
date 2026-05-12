/**
 * 챗봇 모드 API — SSE 스트리밍 (api-spec.md 섹션 1).
 *
 * POST /api/chat 엔드포인트는 SSE 스트림을 반환함.
 * EventSource는 GET만 지원하므로 fetch + ReadableStream 사용.
 *
 * SSE 이벤트:
 *   sources → { sources: [...], confidence: "high" }
 *   token   → { text: "..." }
 *   done    → {}
 *   error   → { message: "..." }
 *
 * 사용처: components/chat/ChatScreen.jsx
 */

const API_BASE = "/api";

/**
 * 챗봇 SSE 스트리밍 요청.
 *
 * @param {string} question - 사용자 질문
 * @param {object} callbacks - { onSources, onToken, onDone, onError }
 *   onSources(data) — 출처 + confidence 수신 시
 *   onToken(text) — 토큰 수신 시
 *   onDone() — 스트리밍 완료 시
 *   onError(message) — 에러 발생 시
 */
export async function streamChat(question, { onSources, onToken, onDone, onError }) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText || "채팅 요청 실패");
  }

  // ReadableStream으로 SSE 이벤트 파싱
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE 이벤트는 빈 줄(\n\n)로 구분
    const events = buffer.split("\n\n");
    buffer = events.pop(); // 마지막 미완성 이벤트는 버퍼에 유지

    for (const eventBlock of events) {
      if (!eventBlock.trim()) continue;

      // SSE 형식 파싱: "event: xxx\ndata: {...}"
      let eventName = null;
      let eventData = null;

      for (const line of eventBlock.split("\n")) {
        if (line.startsWith("event: ")) {
          eventName = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          try {
            eventData = JSON.parse(line.slice(6));
          } catch {
            // JSON 파싱 실패 시 무시
          }
        }
      }

      if (!eventName || eventData === null) continue;

      // 콜백 디스패치
      if (eventName === "sources") onSources?.(eventData);
      else if (eventName === "token") onToken?.(eventData.text);
      else if (eventName === "done") onDone?.();
      else if (eventName === "error") onError?.(eventData.message);
    }
  }
}
