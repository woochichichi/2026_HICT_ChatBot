import { useState } from "react";
import ChatScreen from "./components/chat/ChatScreen";
import TrainingScreen from "./components/training/TrainingScreen";

function App() {
  const [mode, setMode] = useState("training"); // "chat" | "training"

  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: 24 }}>
      <header style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: "1.5rem", color: "#1a1a2e" }}>
          증권 상담원 AI 코치
        </h1>

        {/* 모드 전환 */}
        <div
          style={{
            display: "flex",
            gap: 0,
            marginTop: 16,
            background: "#e2e8f0",
            borderRadius: 8,
            padding: 4,
          }}
        >
          <button
            onClick={() => setMode("chat")}
            style={{
              flex: 1,
              padding: "10px 16px",
              border: "none",
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
              background: mode === "chat" ? "#fff" : "transparent",
              color: mode === "chat" ? "#1e293b" : "#64748b",
              boxShadow: mode === "chat" ? "0 1px 2px rgba(0,0,0,0.06)" : "none",
            }}
          >
            챗봇 모드
          </button>
          <button
            onClick={() => setMode("training")}
            style={{
              flex: 1,
              padding: "10px 16px",
              border: "none",
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
              background: mode === "training" ? "#fff" : "transparent",
              color: mode === "training" ? "#1e293b" : "#64748b",
              boxShadow: mode === "training" ? "0 1px 2px rgba(0,0,0,0.06)" : "none",
            }}
          >
            훈련 모드
          </button>
        </div>
      </header>

      {/* 모드별 화면 전환 — 챗봇(우치), 훈련(승구리) */}
      {mode === "chat" ? <ChatScreen /> : <TrainingScreen />}
    </main>
  );
}

export default App;
