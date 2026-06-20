/** 훈련 모드(AI 코치) API (api-spec.md). */

const API_BASE = "/api";

/**
 * GET /api/training/scenarios — 큐레이션 시나리오 뱅크(커리큘럼/복습용, 런타임 LLM 0).
 */
export async function fetchScenarios() {
  const res = await fetch(`${API_BASE}/training/scenarios`);
  if (!res.ok) throw new Error("시나리오 뱅크를 불러오지 못했습니다.");
  const data = await res.json();
  return data.items || [];
}

/**
 * POST /api/training/question — 질문 생성
 */
export async function fetchQuestion({
  difficulty = "beginner",
  category = "",
  solvedContentIds = [],
  isDemo = false,
  persona = "general",
}) {
  const res = await fetch(`${API_BASE}/training/question`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      difficulty,
      category,
      solved_content_ids: solvedContentIds,
      is_demo: isDemo,
      persona,
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
export async function fetchScore({ questionId, traineeAnswer, persona = "general" }) {
  const res = await fetch(`${API_BASE}/training/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_id: questionId,
      trainee_answer: traineeAnswer,
      persona,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = Array.isArray(err.detail) ? err.detail[0]?.msg : err.detail;
    throw new Error(detail || res.statusText || "채점 실패");
  }

  return res.json();
}
