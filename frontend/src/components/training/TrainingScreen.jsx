import { useState } from "react";
import { fetchQuestion } from "../../api/training";

const DIFFICULTY_LABELS = {
  beginner: "초급",
  intermediate: "중급",
  advanced: "고급",
};

export default function TrainingScreen() {
  const [difficulty, setDifficulty] = useState("beginner");
  const [category, setCategory] = useState("");
  const [isDemo, setIsDemo] = useState(true);
  const [question, setQuestion] = useState(null);
  const [solvedContentIds, setSolvedContentIds] = useState([]);
  const [traineeAnswer, setTraineeAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleFetchQuestion = async () => {
    setLoading(true);
    setError(null);
    setQuestion(null);
    setTraineeAnswer("");

    try {
      const data = await fetchQuestion({
        difficulty,
        category,
        solvedContentIds,
        isDemo,
      });

      setQuestion(data.question);
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

      {question && (
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
            {question}
          </p>
        </div>
      )}

      {question && (
        <div>
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
        </div>
      )}

      {!question && !loading && (
        <p style={{ color: "#94a3b8", fontSize: 14 }}>
          위에서 난이도와 카테고리를 선택한 뒤 "새 질문"을 눌러 시작하세요.
        </p>
      )}
    </section>
  );
}
