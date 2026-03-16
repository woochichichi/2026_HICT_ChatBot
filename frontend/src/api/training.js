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
