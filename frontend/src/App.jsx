/**
 * 앱 셸 — 한화투자증권 AI 상담 어시스턴트.
 * 에이전트-코파일럿 레이아웃: 좌측 사이드바 내비 + 상단바 + 메인 워크스페이스.
 *
 * 모드(내부 토큰은 API 호환 위해 유지):
 *   "chat"     → 응대 모드 (ChatScreen)
 *   "training" → AI 코치   (TrainingScreen)
 *   "review"   → 제보 검토 (ReviewScreen)
 *
 * 스타일: index.css 디자인 시스템(.sidebar/.nav-item/.topbar 등). 아이콘: Icon.jsx(SVG).
 */

import { useState } from "react";
import ChatScreen from "./components/chat/ChatScreen";
import TrainingScreen from "./components/training/TrainingScreen";
import ReviewScreen from "./components/review/ReviewScreen";
import Icon from "./components/common/Icon";
import { PRODUCT_NAME } from "./theme";

const NAV = [
  { key: "chat", icon: "chat", label: "응대 모드", sub: "고객 응대", title: "응대 모드", desc: "업무 편람 기반 실시간 응대 지원" },
  { key: "training", icon: "coach", label: "AI 코치", sub: "응대 훈련", title: "AI 코치", desc: "고객 상황 시뮬레이션 + 응대 채점" },
  { key: "review", icon: "inbox", label: "제보 검토", sub: "운영", title: "제보 검토", desc: "오답 제보 누적 검토 · 답변 품질 개선" },
];

function App() {
  const [mode, setMode] = useState("chat");
  const cur = NAV.find((n) => n.key === mode);

  return (
    <div className="app">
      {/* 사이드바 */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-bar" />
          <div>
            <div className="brand-name">한화투자증권</div>
            <div className="brand-sub">AI 상담 어시스턴트</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-label">워크스페이스</div>
          {NAV.map((n) => (
            <button
              key={n.key}
              className={`nav-item${mode === n.key ? " active" : ""}`}
              onClick={() => setMode(n.key)}
              aria-current={mode === n.key ? "page" : undefined}
            >
              <Icon name={n.icon} size={19} className="nav-ico" />
              <span>{n.label}</span>
              <span className="nav-sub">{n.sub}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-foot">
          <span className="dot" />
          <span>PoC · 로컬 임베딩(bge-m3)</span>
        </div>
      </aside>

      {/* 메인 */}
      <div className="main">
        <header className="topbar">
          <div>
            <h1>{cur.title}</h1>
            <div className="sub">{cur.desc}</div>
          </div>
          <span className="chip">{PRODUCT_NAME}</span>
        </header>

        {mode === "chat" && <ChatScreen />}
        {mode === "training" && <TrainingScreen />}
        {mode === "review" && <ReviewScreen />}
      </div>
    </div>
  );
}

export default App;
