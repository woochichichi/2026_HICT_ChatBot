/** 훈련 모드 API (api-spec.md). */

const API_BASE = "/api";

/**
 * POST /api/training/question — 질문 생성
 */
export async function fetchQuestion({
  difficulty = "beginner",
  category = "",
  solvedContentIds = [],
  isDemo = false,
}) {
  const res = await fetch(`${API_BASE}/training/question`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      difficulty,
      category,
      solved_content_ids: solvedContentIds,
      is_demo: isDemo,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText || "질문 생성 실패");
  }

  return res.json();
}

/**
 * POST /api/training/score — 답변 채점
 */
export async function fetchScore({ questionId, traineeAnswer }) {
  const res = await fetch(`${API_BASE}/training/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_id: questionId,
      trainee_answer: traineeAnswer,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = Array.isArray(err.detail) ? err.detail[0]?.msg : err.detail;
    throw new Error(detail || res.statusText || "채점 실패");
  }

  return res.json();
}
