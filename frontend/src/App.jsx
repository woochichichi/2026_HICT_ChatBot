import TrainingScreen from "./components/training/TrainingScreen";

function App() {
  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: 24 }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: "1.5rem", color: "#1a1a2e" }}>
          증권 상담원 AI 코치
        </h1>
        <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: "0.9rem" }}>
          훈련 모드 — 고객 질문에 답변해 보세요
        </p>
      </header>
      <TrainingScreen />
    </main>
  );
}

export default App;
