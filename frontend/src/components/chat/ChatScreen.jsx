/**
 * 챗봇 모드 UI (api-spec.md 섹션 1).
 *
 * 기능:
 *   - 질문 입력 → SSE 스트리밍 답변 표시
 *   - 출처 패널 (sources 이벤트로 선수신)
 *   - confidence 뱃지 (high/medium/low)
 *   - 메시지 히스토리 (Single-turn이지만 화면에는 대화 형태로 누적)
 *   - AI 답변의 마크다운(**, *, 목록 등) 렌더링
 *
 * SSE 연동: api/chat.js의 streamChat() 사용
 * 스타일: TrainingScreen.jsx와 동일한 inline style 패턴
 */

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { streamChat } from "../../api/chat";

// confidence 수준별 시각 표시 — 현재 UI에서 신뢰도 뱃지는 미표시
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
                  ...(msg.role === "user"
                    ? { background: "#2563eb", color: "#fff", whiteSpace: "pre-wrap" }
                    : { background: "#f1f5f9", color: "#1e293b", border: "1px solid #e2e8f0" }),
                }}
              >
                {/* AI 답변은 마크다운 렌더링, 유저 메시지는 plain text */}
                {msg.role === "assistant" ? (
                  <MarkdownContent content={msg.content} />
                ) : (
                  msg.content
                )}
              </div>
            </div>

            {/* AI 답변의 출처 패널 */}
            {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
              <SourcePanel sources={msg.sources} />
            )}
          </div>
        ))}

        {/* 스트리밍 중인 답변 */}
        {isStreaming && (
          <div>
            {/* 출처 선표시 (sources 이벤트 수신 후) */}
            {currentSources && currentSources.length > 0 && (
              <SourcePanel sources={currentSources} />
            )}
            <div style={{ display: "flex", justifyContent: "flex-start" }}>
              <div
                style={{
                  maxWidth: "80%",
                  padding: "10px 14px",
                  borderRadius: 12,
                  fontSize: 15,
                  lineHeight: 1.6,
                  background: "#f1f5f9",
                  color: "#1e293b",
                  border: "1px solid #e2e8f0",
                }}
              >
                {streamingText ? (
                  <MarkdownContent content={streamingText} />
                ) : (
                  "답변 생성 중..."
                )}
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
 * 마크다운 렌더링 컴포넌트.
 * AI 답변의 **굵게**, *기울임*, 목록, 헤딩 등을 HTML로 변환.
 * react-markdown 사용 + 인라인 스타일로 기본 시각 표현.
 */
function MarkdownContent({ content }) {
  return (
    <ReactMarkdown
      components={{
        // 단락
        p: ({ children }) => (
          <p style={{ margin: "4px 0", lineHeight: 1.7 }}>{children}</p>
        ),
        // 굵게
        strong: ({ children }) => (
          <strong style={{ fontWeight: 700 }}>{children}</strong>
        ),
        // 기울임
        em: ({ children }) => (
          <em style={{ fontStyle: "italic" }}>{children}</em>
        ),
        // 비순서 목록 (*, -, +)
        ul: ({ children }) => (
          <ul style={{ margin: "6px 0", paddingLeft: 20 }}>{children}</ul>
        ),
        // 순서 목록
        ol: ({ children }) => (
          <ol style={{ margin: "6px 0", paddingLeft: 20 }}>{children}</ol>
        ),
        // 목록 항목
        li: ({ children }) => (
          <li style={{ margin: "3px 0", lineHeight: 1.6 }}>{children}</li>
        ),
        // 헤딩 H1~H3
        h1: ({ children }) => (
          <h1 style={{ fontSize: 18, fontWeight: 700, margin: "10px 0 4px" }}>{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: "8px 0 4px" }}>{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 style={{ fontSize: 15, fontWeight: 600, margin: "6px 0 4px" }}>{children}</h3>
        ),
        // 인라인 코드
        code: ({ children }) => (
          <code style={{ background: "#e2e8f0", borderRadius: 4, padding: "1px 5px", fontSize: 13 }}>
            {children}
          </code>
        ),
        // 구분선
        hr: () => <hr style={{ border: "none", borderTop: "1px solid #e2e8f0", margin: "8px 0" }} />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

/**
 * 출처 패널 컴포넌트 — 기본 접힌 상태, 클릭 시 토글.
 * 신뢰도 정보는 미표시, 출처 목록만 표시.
 */
function SourcePanel({ sources }) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ marginTop: 4, marginBottom: 2, marginLeft: 8 }}>
      {/* 토글 버튼 */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "3px 10px 3px 8px",
          borderRadius: 6,
          border: "1px solid #e2e8f0",
          background: "#f8fafc",
          cursor: "pointer",
          fontSize: 12,
          color: "#64748b",
        }}
      >
        <span>출처 {sources.length}건</span>
        <span
          style={{
            fontSize: 10,
            display: "inline-block",
            transition: "transform 0.2s",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
          }}
        >
          ▼
        </span>
      </button>

      {/* 펼쳐진 출처 목록 */}
      {open && (
        <div
          style={{
            marginTop: 6,
            padding: "8px 12px",
            background: "#f8fafc",
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            fontSize: 12,
            color: "#64748b",
          }}
        >
          {sources.map((src, i) => (
            <div key={i} style={{ marginTop: i > 0 ? 6 : 0, lineHeight: 1.5 }}>
              <span style={{ fontWeight: 600, color: "#475569" }}>[{i + 1}]</span>{" "}
              {src.title}
              <span style={{ marginLeft: 6, fontSize: 11, color: "#94a3b8" }}>
                ({(src.relevance_score * 100).toFixed(0)}%)
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
