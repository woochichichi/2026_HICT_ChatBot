import { useState } from "react";
import { fetchQuestion, fetchScore } from "../../api/training";

const DIFFICULTY_LABELS = {
  beginner: "초급",
  intermediate: "중급",
  advanced: "고급",
};

export default function TrainingScreen() {
  const [difficulty, setDifficulty] = useState("beginner");
  const [category, setCategory] = useState("");
  const [isDemo, setIsDemo] = useState(true);
  const [questionData, setQuestionData] = useState(null);
  const [solvedContentIds, setSolvedContentIds] = useState([]);
  const [traineeAnswer, setTraineeAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [scoreResult, setScoreResult] = useState(null);

  const handleFetchQuestion = async () => {
    setLoading(true);
    setError(null);
    setQuestionData(null);
    setTraineeAnswer("");
    setScoreResult(null);

    try {
      const data = await fetchQuestion({
        difficulty,
        category,
        solvedContentIds,
        isDemo,
      });

      setQuestionData(data);
      setSolvedContentIds((prev) =>
        data.is_reset
          ? [data.source_content_id]
          : [...prev, data.source_content_id].filter(Boolean)
      );
    } catch (err) {
      setError(err.message || "질문을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!questionData?.question_id || !traineeAnswer.trim()) {
      setError("답변을 입력해 주세요.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setScoreResult(null);

    try {
      const result = await fetchScore({
        questionId: questionData.question_id,
        traineeAnswer: traineeAnswer.trim(),
      });
      setScoreResult(result);
    } catch (err) {
      setError(err.message || "채점에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section
      style={{
        background: "#fff",
        borderRadius: 12,
        padding: 24,
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 12 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, color: "#64748b" }}>난이도</span>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              style={{
                padding: "6px 10px",
                borderRadius: 6,
                border: "1px solid #e2e8f0",
                fontSize: 14,
              }}
            >
              <option value="beginner">초급</option>
              <option value="intermediate">중급</option>
              <option value="advanced">고급</option>
            </select>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, color: "#64748b" }}>카테고리</span>
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="계좌, 매매 등"
              style={{
                padding: "6px 10px",
                borderRadius: 6,
                border: "1px solid #e2e8f0",
                fontSize: 14,
                width: 160,
              }}
            />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={isDemo}
              onChange={(e) => setIsDemo(e.target.checked)}
            />
            <span style={{ fontSize: 14, color: "#64748b" }}>데모 모드</span>
          </label>
        </div>
        <button
          onClick={handleFetchQuestion}
          disabled={loading}
          style={{
            padding: "10px 20px",
            borderRadius: 8,
            border: "none",
            background: loading ? "#cbd5e1" : "#2563eb",
            color: "#fff",
            fontSize: 14,
            fontWeight: 500,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "질문 생성 중…" : "새 질문"}
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: 12,
            marginBottom: 16,
            background: "#fef2f2",
            color: "#b91c1c",
            borderRadius: 8,
            fontSize: 14,
          }}
        >
          {error}
        </div>
      )}

      {questionData && (
        <div
          style={{
            marginBottom: 20,
            padding: 16,
            background: "#f8fafc",
            borderRadius: 8,
            borderLeft: "4px solid #2563eb",
          }}
        >
          <p
            style={{
              margin: "0 0 8px",
              fontSize: 12,
              color: "#64748b",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            고객 질문 {DIFFICULTY_LABELS[difficulty] || difficulty}
          </p>
          <p style={{ margin: 0, fontSize: 16, lineHeight: 1.6, color: "#1e293b" }}>
            {questionData.question}
          </p>
          {questionData.reference && (
            <p
              style={{
                margin: "12px 0 0",
                fontSize: 13,
                color: "#475569",
                padding: "8px 10px",
                background: "#e2e8f0",
                borderRadius: 6,
              }}
            >
              📖 편람 내 위치: {questionData.reference}
            </p>
          )}
        </div>
      )}

      {questionData && (
        <div style={{ marginBottom: 16 }}>
          <label
            style={{
              display: "block",
              marginBottom: 8,
              fontSize: 14,
              fontWeight: 500,
              color: "#334155",
            }}
          >
            내 답변
          </label>
          <textarea
            value={traineeAnswer}
            onChange={(e) => setTraineeAnswer(e.target.value)}
            placeholder="고객 질문에 대한 답변을 입력하세요..."
            rows={6}
            style={{
              width: "100%",
              padding: 12,
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              fontSize: 15,
              lineHeight: 1.6,
              resize: "vertical",
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{
              marginTop: 12,
              padding: "10px 24px",
              borderRadius: 8,
              border: "none",
              background: submitting ? "#cbd5e1" : "#059669",
              color: "#fff",
              fontSize: 14,
              fontWeight: 500,
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            {submitting ? "채점 중…" : "제출"}
          </button>
        </div>
      )}

      {scoreResult && (
        <div
          style={{
            marginTop: 24,
            padding: 20,
            background: "#f0fdf4",
            borderRadius: 12,
            border: "1px solid #bbf7d0",
          }}
        >
          <h3 style={{ margin: "0 0 16px", fontSize: 18, color: "#166534" }}>
            채점 결과 — {scoreResult.score}점
          </h3>
          <p style={{ margin: "0 0 12px", fontSize: 14, lineHeight: 1.6, color: "#1e293b" }}>
            {scoreResult.feedback}
          </p>
          {scoreResult.included_items?.length > 0 && (
            <p style={{ margin: "0 0 4px", fontSize: 13, color: "#15803d" }}>
              ✓ 포함: {scoreResult.included_items.join(", ")}
            </p>
          )}
          {scoreResult.missing_items?.length > 0 && (
            <p style={{ margin: "0 0 4px", fontSize: 13, color: "#b91c1c" }}>
              ✗ 누락: {scoreResult.missing_items.join(", ")}
            </p>
          )}
          {scoreResult.reference && (
            <p
              style={{
                margin: "12px 0 0",
                padding: "8px 10px",
                background: "#e0f2fe",
                borderRadius: 6,
                fontSize: 13,
                color: "#0369a1",
              }}
            >
              📖 편람 내 위치: {scoreResult.reference}
            </p>
          )}
          {scoreResult.model_answer && (
            <details style={{ marginTop: 12 }}>
              <summary style={{ fontSize: 13, color: "#475569", cursor: "pointer" }}>
                모범 답변 보기
              </summary>
              <p
                style={{
                  marginTop: 8,
                  padding: 12,
                  background: "#fff",
                  borderRadius: 8,
                  fontSize: 14,
                  lineHeight: 1.6,
                  color: "#334155",
                }}
              >
                {scoreResult.model_answer}
              </p>
            </details>
          )}
        </div>
      )}

      {!questionData && !loading && (
        <p style={{ color: "#94a3b8", fontSize: 14 }}>
          위에서 난이도와 카테고리를 선택한 뒤 "새 질문"을 눌러 시작하세요.
        </p>
      )}
    </section>
  );
}
