/**
 * 오답 제보(피드백) API 클라이언트 (api-spec.md 섹션 11).
 *
 * 사용처:
 *   - components/chat/ChatScreen.jsx — submitFeedback (제보 모달)
 *   - components/review/ReviewScreen.jsx — listFeedback / resolveFeedback (검토)
 *
 * 패턴은 api/training.js 와 동일(fetch + JSON).
 */

const API_BASE = "/api";

/**
 * POST /api/feedback — 오답 제보 등록.
 * @param {{question, answer, reason, suggested?, sources?, confidence?}} payload
 */
export async function submitFeedback(payload) {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = Array.isArray(err.detail) ? err.detail[0]?.msg : err.detail;
    throw new Error(detail || res.statusText || "제보 전송 실패");
  }
  return res.json();
}

/**
 * GET /api/feedback?status= — 제보 목록 조회.
 * @param {"open"|"resolved"|undefined} status
 * @returns {Promise<{items: Array}>}
 */
export async function listFeedback(status) {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const res = await fetch(`${API_BASE}/feedback${qs}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText || "제보 목록 조회 실패");
  }
  return res.json();
}

/**
 * POST /api/feedback/{id}/resolve — 처리완료 전환.
 */
export async function resolveFeedback(feedbackId, note) {
  const qs = note ? `?note=${encodeURIComponent(note)}` : "";
  const res = await fetch(`${API_BASE}/feedback/${feedbackId}/resolve${qs}`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText || "처리 실패");
  }
  return res.json();
}
