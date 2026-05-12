/**
 * 챗봇 모드 UI (api-spec.md 섹션 1).
 *
 * 기능:
 *   - 질문 입력 → SSE 스트리밍 답변 표시
 *   - 출처 패널 (sources 이벤트로 선수신)
 *   - confidence 뱃지 (high/medium/low)
 *   - 메시지 히스토리 (Single-turn이지만 화면에는 대화 형태로 누적)
 *
 * SSE 연동: api/chat.js의 streamChat() 사용
 * 스타일: TrainingScreen.jsx와 동일한 inline style 패턴
 */

import { useState, useRef, useEffect } from "react";
import { streamChat } from "../../api/chat";

// confidence 수준별 시각 표시 (api-spec.md: high ≥0.85, medium 0.70~0.85, low <0.70)
const CONFIDENCE_STYLE = {
  high: { label: "높음", color: "#16a34a", bg: "#f0fdf4" },
  medium: { label: "보통", color: "#ca8a04", bg: "#fefce8" },
  low: { label: "낮음", color: "#dc2626", bg: "#fef2f2" },
};

export default function ChatScreen() {
  // messages: 대화 히스토리 — { role, content, sources?, confidence? }
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  // 스트리밍 중 실시간 텍스트 누적용
  const [streamingText, setStreamingText] = useState("");
  // 현재 스트리밍 중인 답변의 출처 정보
  const [currentSources, setCurrentSources] = useState(null);
  const [currentConfidence, setCurrentConfidence] = useState(null);
  const [error, setError] = useState(null);

  // ref로 최신 sources/confidence 유지 — onDone closure에서 stale 값 방지
  const sourcesRef = useRef(null);
  const confidenceRef = useRef(null);

  // 메시지 목록 자동 스크롤
  const messagesEndRef = useRef(null);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  const handleSubmit = async () => {
    const question = input.trim();
    if (!question || isStreaming) return;

    // 유저 메시지 추가
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setIsStreaming(true);
    setStreamingText("");
    setCurrentSources(null);
    setCurrentConfidence(null);
    setError(null);

    try {
      await streamChat(question, {
        // 1. sources 이벤트 — 출처 + confidence 선수신
        onSources: (data) => {
          const sources = data.sources || [];
          const confidence = data.confidence || "low";
          setCurrentSources(sources);
          setCurrentConfidence(confidence);
          // ref에도 저장 — onDone closure에서 최신값 접근용
          sourcesRef.current = sources;
          confidenceRef.current = confidence;
        },
        // 2. token 이벤트 — 실시간 텍스트 누적
        onToken: (text) => {
          setStreamingText((prev) => prev + text);
        },
        // 3. done 이벤트 — 스트리밍 완료, 메시지 히스토리에 확정
        onDone: () => {
          setStreamingText((prev) => {
            // ref에서 최신값 읽기 (closure stale 문제 방지)
            setMessages((msgs) => [
              ...msgs,
              {
                role: "assistant",
                content: prev,
                sources: sourcesRef.current,
                confidence: confidenceRef.current,
              },
            ]);
            return "";
          });
          setIsStreaming(false);
        },
        // 4. error 이벤트
        onError: (message) => {
          setError(message || "답변 생성 중 에러가 발생했습니다.");
          setIsStreaming(false);
        },
      });
    } catch (err) {
      setError(err.message || "서버 연결 실패");
      setIsStreaming(false);
    }
  };

  // Enter로 전송, Shift+Enter로 줄바꿈
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <section
      style={{
        background: "#fff",
        borderRadius: 12,
        padding: 24,
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 160px)",
      }}
    >
      {/* 메시지 목록 */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          marginBottom: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {messages.length === 0 && !isStreaming && (
          <p style={{ color: "#94a3b8", fontSize: 14, textAlign: "center", marginTop: 40 }}>
            업무 편람에 대해 질문해 보세요.
          </p>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            {/* 메시지 본문 */}
            <div
              style={{
                display: "flex",
                justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  maxWidth: "80%",
                  padding: "10px 14px",
                  borderRadius: 12,
                  fontSize: 15,
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                  ...(msg.role === "user"
                    ? { background: "#2563eb", color: "#fff" }
                    : { background: "#f1f5f9", color: "#1e293b", border: "1px solid #e2e8f0" }),
                }}
              >
                {msg.content}
              </div>
            </div>

            {/* AI 답변의 출처 패널 */}
            {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
              <SourcePanel sources={msg.sources} confidence={msg.confidence} />
            )}
          </div>
        ))}

        {/* 스트리밍 중인 답변 */}
        {isStreaming && (
          <div>
            {/* 출처 선표시 (sources 이벤트 수신 후) */}
            {currentSources && currentSources.length > 0 && (
              <SourcePanel sources={currentSources} confidence={currentConfidence} />
            )}
            <div style={{ display: "flex", justifyContent: "flex-start" }}>
              <div
                style={{
                  maxWidth: "80%",
                  padding: "10px 14px",
                  borderRadius: 12,
                  fontSize: 15,
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                  background: "#f1f5f9",
                  color: "#1e293b",
                  border: "1px solid #e2e8f0",
                }}
              >
                {streamingText || "답변 생성 중..."}
                <span style={{ animation: "blink 1s infinite", opacity: 0.5 }}>|</span>
              </div>
            </div>
          </div>
        )}

        {/* 에러 표시 */}
        {error && (
          <div
            style={{
              padding: 12,
              background: "#fef2f2",
              color: "#b91c1c",
              borderRadius: 8,
              fontSize: 14,
            }}
          >
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 입력 영역 */}
      <div style={{ display: "flex", gap: 8 }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="질문을 입력하세요... (Enter로 전송)"
          rows={1}
          disabled={isStreaming}
          style={{
            flex: 1,
            padding: "10px 14px",
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            fontSize: 15,
            lineHeight: 1.5,
            resize: "none",
            outline: "none",
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={isStreaming || !input.trim()}
          style={{
            padding: "10px 20px",
            borderRadius: 8,
            border: "none",
            background: isStreaming || !input.trim() ? "#cbd5e1" : "#2563eb",
            color: "#fff",
            fontSize: 14,
            fontWeight: 500,
            cursor: isStreaming || !input.trim() ? "not-allowed" : "pointer",
          }}
        >
          전송
        </button>
      </div>
    </section>
  );
}

/**
 * 출처 패널 컴포넌트.
 * RAG 검색 결과의 출처 목록과 confidence 뱃지를 표시.
 */
function SourcePanel({ sources, confidence }) {
  const conf = CONFIDENCE_STYLE[confidence] || CONFIDENCE_STYLE.low;

  return (
    <div
      style={{
        marginTop: 6,
        marginBottom: 4,
        marginLeft: 8,
        padding: "8px 12px",
        background: "#f8fafc",
        borderRadius: 8,
        fontSize: 13,
        color: "#64748b",
      }}
    >
      {/* Confidence 뱃지 */}
      <span
        style={{
          display: "inline-block",
          padding: "2px 8px",
          borderRadius: 4,
          fontSize: 12,
          fontWeight: 500,
          color: conf.color,
          background: conf.bg,
          marginBottom: 4,
        }}
      >
        신뢰도: {conf.label}
      </span>

      {/* 출처 목록 */}
      <div style={{ marginTop: 4 }}>
        {sources.map((src, i) => (
          <div key={i} style={{ marginTop: 2 }}>
            [{i + 1}] {src.title}
            <span style={{ marginLeft: 8, fontSize: 11, color: "#94a3b8" }}>
              (유사도: {(src.relevance_score * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
