/**
 * 응대 모드 — RAG 채팅(에이전트-코파일럿 패턴, api-spec.md 섹션 1).
 *
 * UX 패턴(웹 리서치 반영):
 *   - 출처를 답변보다 먼저(SSE) + 클릭 가능한 출처 카드
 *   - 신뢰도 칩(high/medium/low) 노출
 *   - 토큰 스트리밍 + 타이핑 인디케이터 + 중지 버튼
 *   - 답변마다 오답 제보(피드백) — 정합성 체크
 *   - 빈 상태: 예시 프롬프트(capability transparency)
 *   - 접근성: aria-live(스트리밍), aria-label(아이콘 버튼), focus 링
 *
 * 스타일: index.css(.chat/.bubble/.src-card/.composer 등). 아이콘: Icon.jsx.
 */

import { useState, useRef, useEffect } from "react";
import { streamChat } from "../../api/chat";
import { submitFeedback } from "../../api/feedback";
import { CANNED_ANSWERS } from "../../data/cannedAnswers";
import Icon from "../common/Icon";
import Markdown from "../common/Markdown";
import { CONFIDENCE_STYLE } from "../../theme";

// 예시 칩 = 사전 제작 답변 키 (LLM 미사용, 시연 안정)
const SUGGESTIONS = Object.keys(CANNED_ANSWERS);

export default function ChatScreen() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [currentSources, setCurrentSources] = useState(null);
  const [error, setError] = useState(null);
  const [reportTarget, setReportTarget] = useState(null);
  const [reportToast, setReportToast] = useState(null);

  const sourcesRef = useRef(null);
  const confidenceRef = useRef(null);
  const streamRef = useRef(""); // 중지 시 부분 답변 확정용
  const abortRef = useRef(null);
  const taRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  // textarea 자동 높이
  const autosize = () => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  // 스트리밍 답변을 메시지로 확정(실제/캔드 공통)
  const commit = () => {
    setMessages((msgs) => [
      ...msgs,
      {
        role: "assistant",
        content: streamRef.current,
        sources: sourcesRef.current,
        confidence: confidenceRef.current,
      },
    ]);
    setStreamingText("");
    streamRef.current = "";
    setIsStreaming(false);
  };

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || isStreaming) return;

    setInput("");
    if (taRef.current) taRef.current.style.height = "auto";
    setError(null);

    // 예시 칩 = 사전 제작 답변 → 즉시 표시(LLM 미사용, 시연 안정)
    const canned = CANNED_ANSWERS[question];
    if (canned) {
      setMessages((p) => [
        ...p,
        { role: "user", content: question },
        {
          role: "assistant",
          content: canned.answer,
          sources: canned.sources || [],
          confidence: canned.confidence || "high",
        },
      ]);
      return;
    }

    // 일반 질문 = 실시간 RAG 스트리밍
    setMessages((p) => [...p, { role: "user", content: question }]);
    setIsStreaming(true);
    setStreamingText("");
    streamRef.current = "";
    setCurrentSources(null);
    sourcesRef.current = null;
    confidenceRef.current = null;

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      await streamChat(question, {
        signal: ctrl.signal,
        onSources: (data) => {
          const sources = data.sources || [];
          const confidence = data.confidence || "low";
          setCurrentSources(sources);
          sourcesRef.current = sources;
          confidenceRef.current = confidence;
        },
        onToken: (t) => {
          streamRef.current += t;
          setStreamingText((p) => p + t);
        },
        onDone: () => commit(),
        onError: (m) => {
          setError(m || "답변 생성 중 오류가 발생했습니다.");
          setStreamingText("");
          streamRef.current = "";
          setIsStreaming(false);
        },
      });
    } catch (err) {
      if (err?.name === "AbortError") {
        if (streamRef.current) commit();
        else setIsStreaming(false);
      } else {
        setError(err.message || "서버 연결에 실패했습니다.");
        setIsStreaming(false);
      }
    }
  };

  const stop = () => abortRef.current?.abort();

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const showEmpty = messages.length === 0 && !isStreaming && !error;

  return (
    <section className="chat">
      <div className="thread">
        {showEmpty ? (
          <div className="empty">
            <span className="badge">
              <Icon name="sparkles" size={26} />
            </span>
            <h2>무엇을 도와드릴까요?</h2>
            <p>업무 편람·FAQ에서 근거(출처)와 함께 답변합니다. 아래 예시로 시작해 보세요.</p>
            <div className="suggests">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggest" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="thread-inner">
            {messages.map((msg, i) =>
              msg.role === "user" ? (
                <div key={i} className="row user">
                  <div className="bubble me">{msg.content}</div>
                </div>
              ) : (
                <div key={i}>
                  <div className="row">
                    <span className="avatar">
                      <Icon name="sparkles" size={18} />
                    </span>
                    <div className="bubble ai">
                      <Markdown content={msg.content} />
                    </div>
                  </div>
                  {msg.sources && msg.sources.length > 0 && <Sources sources={msg.sources} />}
                  <div className="answer-meta">
                    {msg.confidence && CONFIDENCE_STYLE[msg.confidence] && (
                      <span className={`chip conf-${msg.confidence}`}>
                        <Icon name="shield" size={13} />
                        신뢰도 {CONFIDENCE_STYLE[msg.confidence].label}
                      </span>
                    )}
                    <button
                      className="feedback-link"
                      onClick={() =>
                        setReportTarget({
                          question: messages[i - 1]?.content ?? "",
                          answer: msg.content,
                          sources: msg.sources ?? [],
                          confidence: msg.confidence ?? "low",
                        })
                      }
                    >
                      <Icon name="flag" size={13} /> 오답 제보
                    </button>
                  </div>
                </div>
              )
            )}

            {/* 스트리밍 중 */}
            {isStreaming && (
              <div>
                {currentSources && currentSources.length > 0 && <Sources sources={currentSources} />}
                <div className="row">
                  <span className="avatar">
                    <Icon name="sparkles" size={18} />
                  </span>
                  <div className="bubble ai" aria-live="polite">
                    {streamingText ? (
                      <>
                        <Markdown content={streamingText} />
                        <span className="caret">▏</span>
                      </>
                    ) : (
                      <span className="typing">
                        <i /><i /><i />
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="banner-error">
                <Icon name="shield" size={16} /> {error}
              </div>
            )}

            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* 컴포저 */}
      <div className="composer-wrap">
        <div className="composer">
          <div className="composer-box">
            <button
              type="button"
              className="btn btn-icon btn-ghost"
              disabled
              aria-label="음성 입력(STT) 준비 중"
              title="음성 입력(STT) 연동 예정 — 통화 내용을 자동으로 질문에 입력"
            >
              <Icon name="mic" size={19} />
            </button>
            <textarea
              ref={taRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                autosize();
              }}
              onKeyDown={onKey}
              placeholder="업무 편람에 대해 질문하세요. (Enter 전송 · Shift+Enter 줄바꿈)"
              rows={1}
              aria-label="질문 입력"
            />
            {isStreaming ? (
              <button className="btn btn-icon" onClick={stop} aria-label="생성 중지" title="생성 중지">
                <Icon name="stop" size={16} />
              </button>
            ) : (
              <button
                className="btn btn-icon btn-primary"
                onClick={() => send()}
                disabled={!input.trim()}
                aria-label="전송"
                title="전송"
              >
                <Icon name="send" size={18} />
              </button>
            )}
          </div>
          <div className="composer-hint">
            답변은 업무 편람을 근거로 생성되며, 출처로 확인할 수 있습니다.
          </div>
        </div>
      </div>

      {reportToast && (
        <div className="toast">
          <Icon name="check" size={16} /> {reportToast}
        </div>
      )}
      {reportTarget && (
        <ReportModal
          target={reportTarget}
          onClose={() => setReportTarget(null)}
          onSubmitted={(id) => {
            setReportTarget(null);
            setReportToast(`제보가 접수되었습니다 (#${id}). 감사합니다.`);
            setTimeout(() => setReportToast(null), 3000);
          }}
        />
      )}
    </section>
  );
}

/* 출처 카드 목록 */
function Sources({ sources }) {
  return (
    <div className="sources">
      <span className="sources-head">출처 {sources.length}건</span>
      {sources.map((s, i) => {
        const inner = (
          <>
            <span className="src-idx">{i + 1}</span>
            <span className="src-title">{s.title}</span>
            {typeof s.relevance_score === "number" && (
              <span className="src-score">{(s.relevance_score * 100).toFixed(0)}%</span>
            )}
            {s.url && <Icon name="external" size={14} style={{ color: "var(--gray-400)" }} />}
          </>
        );
        return s.url ? (
          <a key={i} className="src-card" href={s.url} target="_blank" rel="noopener noreferrer">
            {inner}
          </a>
        ) : (
          <div key={i} className="src-card">
            {inner}
          </div>
        );
      })}
    </div>
  );
}

/* 오답 제보 모달 */
function ReportModal({ target, onClose, onSubmitted }) {
  const [reason, setReason] = useState("");
  const [suggested, setSuggested] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async () => {
    if (!reason.trim()) {
      setErr("제보 사유를 입력해 주세요.");
      return;
    }
    setSubmitting(true);
    setErr(null);
    try {
      const res = await submitFeedback({
        question: target.question,
        answer: target.answer,
        reason: reason.trim(),
        suggested: suggested.trim() || null,
        sources: target.sources,
        confidence: target.confidence,
      });
      onSubmitted(res.id);
    } catch (e) {
      setErr(e.message || "제보 전송에 실패했습니다.");
      setSubmitting(false);
    }
  };

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-head">
          <h3>
            <Icon name="flag" size={18} style={{ color: "var(--orange)" }} /> 오답 제보
          </h3>
          <button className="btn btn-icon btn-ghost" onClick={onClose} aria-label="닫기">
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className="modal-body">
          <p style={{ margin: "0 0 14px", fontSize: 13, color: "var(--gray-500)" }}>
            답변의 정합성 문제를 알려주세요. 검토 후 편람·답변 개선에 반영됩니다.
          </p>

          <div
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--line)",
              borderRadius: "var(--r-sm)",
              padding: 12,
              marginBottom: 16,
              fontSize: 13,
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gray-400)" }}>질문</div>
            <div style={{ margin: "2px 0 8px", color: "var(--ink)" }}>{target.question || "(질문 없음)"}</div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gray-400)" }}>AI 답변</div>
            <div style={{ marginTop: 2, color: "var(--gray-700)", maxHeight: 140, overflowY: "auto" }}>
              <Markdown content={target.answer} />
            </div>
          </div>

          <label className="lbl" htmlFor="fb-reason">
            제보 사유 <span style={{ color: "var(--bad)" }}>*</span>
          </label>
          <textarea
            id="fb-reason"
            className="field"
            style={{ width: "100%", marginTop: 6, resize: "vertical" }}
            rows={3}
            autoFocus
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="예: 수수료율이 편람과 다릅니다 / 절차 일부가 누락됐습니다"
          />

          <label className="lbl" htmlFor="fb-sug" style={{ display: "block", marginTop: 14 }}>
            정답 제안 <span style={{ color: "var(--gray-400)", fontWeight: 400 }}>(선택)</span>
          </label>
          <textarea
            id="fb-sug"
            className="field"
            style={{ width: "100%", marginTop: 6, resize: "vertical" }}
            rows={3}
            value={suggested}
            onChange={(e) => setSuggested(e.target.value)}
            placeholder="올바른 답변/안내가 있다면 적어주세요."
          />

          {err && (
            <div className="banner-error" style={{ marginTop: 12 }}>
              <Icon name="shield" size={15} /> {err}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 18 }}>
            <button className="btn" onClick={onClose} disabled={submitting}>
              취소
            </button>
            <button className="btn btn-primary" onClick={submit} disabled={submitting || !reason.trim()}>
              {submitting ? "전송 중…" : "제보하기"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
