/**
 * AI 코치 — 응대 상황 시뮬레이션 + 채점 (api-spec.md 섹션 1·11).
 *
 * 코칭/롤플레이 툴(Second Nature·Hyperbound·Zenarate) 패턴 반영:
 *   시나리오 설정 → 페르소나(고객 상황) 카드 → 롤플레이(출제→응대) → 스코어카드.
 *   스코어카드 = 종합점수(링) + 루브릭 분해(바) + 포함/누락 + '다음 행동' 코칭 + 모범답변.
 *   세션 진척(문항 수·평균)도 추적(코칭툴 공통).
 *
 * 스타일: index.css(.persona-card/.seg/.bar/.coach-tips/.score-ring). 아이콘: Icon.jsx.
 */

import { useState, useEffect } from "react";
import { fetchQuestion, fetchScore } from "../../api/training";
import Icon from "../common/Icon";
import { speak, cancelSpeak, ttsSupported } from "../../lib/tts";

const DIFFICULTIES = [
  { value: "beginner", label: "초급" },
  { value: "intermediate", label: "중급" },
  { value: "advanced", label: "고급" },
];
const DIFFICULTY_LABELS = Object.fromEntries(DIFFICULTIES.map((d) => [d.value, d.label]));

// 고객 상황(페르소나) 8종 — 콜센터에서 자주 겪고 애먹는 유형(화남·무리한요구·조급·고령·
// 불안 등) + 증권 맥락. 백엔드 PERSONA_GUIDES/NOTES/DEMO_TEMPLATE와 키 일치.
const PERSONAS = [
  { value: "standard", icon: "user", label: "일반 고객", desc: "표준 문의" },
  { value: "angry", icon: "alert", label: "화난 고객", desc: "불만·항의가 거셈" },
  { value: "impatient", icon: "clock", label: "급한 고객", desc: "빠른 답을 원함" },
  { value: "elderly", icon: "help", label: "고령 고객", desc: "용어 어려움·천천히" },
  { value: "anxious", icon: "heart", label: "불안한 고객", desc: "손실 걱정·안심 필요" },
  { value: "demanding", icon: "hand", label: "무리한 요구", desc: "규정 밖 요구" },
  { value: "talkative", icon: "chat", label: "말 많은 고객", desc: "장황·곁가지" },
  { value: "skeptical", icon: "search", label: "따지는 고객", desc: "근거·확인 요구" },
];
const PERSONA_MAP = Object.fromEntries(PERSONAS.map((p) => [p.value, p]));

// 페르소나별 음성 톤(rate=속도, pitch=음높이). 기본 음성은 '나이 많은 남성'(tts.js),
// 여기서 상황별로 미세 조정. 고령은 느리게, 급한 고객은 빠르게, 화남/무리요구는 낮고 단호.
const PERSONA_VOICE = {
  standard: { rate: 0.98, pitch: 0.96 },
  angry: { rate: 1.04, pitch: 0.9 },
  impatient: { rate: 1.12, pitch: 0.98 },
  elderly: { rate: 0.86, pitch: 0.92 },
  anxious: { rate: 0.96, pitch: 0.98 },
  demanding: { rate: 1.02, pitch: 0.92 },
  talkative: { rate: 0.98, pitch: 0.98 },
  skeptical: { rate: 0.98, pitch: 0.94 },
};

export default function TrainingScreen() {
  const [difficulty, setDifficulty] = useState("beginner");
  const [persona, setPersona] = useState("standard");
  const [isDemo, setIsDemo] = useState(true);
  const [questionData, setQuestionData] = useState(null);
  const [solvedContentIds, setSolvedContentIds] = useState([]);
  const [traineeAnswer, setTraineeAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [scoreResult, setScoreResult] = useState(null);
  const [activePersona, setActivePersona] = useState("standard");
  const [history, setHistory] = useState([]); // 세션 점수 누적
  const [autoRead, setAutoRead] = useState(true); // 시나리오 음성 자동재생
  const [speaking, setSpeaking] = useState(false);

  // 화면 이탈/언마운트 시 낭독 중단
  useEffect(() => () => cancelSpeak(), []);

  // 시나리오를 고객 음성으로 낭독(폐쇄망: 브라우저 로컬 TTS)
  const readScenario = (text, personaKey) => {
    const vp = PERSONA_VOICE[personaKey] || PERSONA_VOICE.standard;
    speak(text, {
      ...vp, // rate/pitch: 브라우저 폴백용
      persona: personaKey, // 서버 신경망 TTS 톤
      onstart: () => setSpeaking(true),
      onend: () => setSpeaking(false),
    });
  };

  const newQuestion = async () => {
    cancelSpeak();
    setSpeaking(false);
    setLoading(true);
    setError(null);
    setQuestionData(null);
    setTraineeAnswer("");
    setScoreResult(null);
    try {
      const data = await fetchQuestion({ difficulty, solvedContentIds, isDemo, persona });
      setQuestionData(data);
      setActivePersona(persona);
      if (autoRead) readScenario(data.question, persona); // 고객 음성으로 낭독
      setSolvedContentIds((prev) =>
        data.is_reset ? [data.source_content_id] : [...prev, data.source_content_id].filter(Boolean)
      );
    } catch (err) {
      setError(err.message || "질문을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const submit = async () => {
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
        persona: activePersona,
      });
      setScoreResult(result);
      setHistory((h) => [...h, result.score]);
    } catch (err) {
      setError(err.message || "채점에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  const avg = history.length ? Math.round(history.reduce((a, b) => a + b, 0) / history.length) : null;
  const pc = PERSONA_MAP[activePersona] || PERSONAS[0];

  return (
    <div className="content">
      <div className="content-pad" style={{ maxWidth: 780 }}>
        {/* 시나리오 설정 */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <h2 style={{ margin: 0, fontSize: 15, color: "var(--ink)", display: "flex", alignItems: "center", gap: 7 }}>
              <Icon name="target" size={17} style={{ color: "var(--orange)" }} /> 시나리오 설정
            </h2>
            {history.length > 0 && (
              <div className="progress-strip">
                <div>
                  <div className="pv">{history.length}</div>
                  <div className="pl">완료 문항</div>
                </div>
                <div>
                  <div className="pv">{avg}<span style={{ fontSize: 12, color: "var(--gray-400)" }}> 점</span></div>
                  <div className="pl">평균 점수</div>
                </div>
              </div>
            )}
          </div>

          {/* 난이도 */}
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16, flexWrap: "wrap" }}>
            <label className="lbl" style={{ minWidth: 56 }}>난이도</label>
            <div className="seg">
              {DIFFICULTIES.map((d) => (
                <button key={d.value} className={difficulty === d.value ? "on" : ""} onClick={() => setDifficulty(d.value)}>
                  {d.label}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 16, marginLeft: "auto", flexWrap: "wrap" }}>
              {ttsSupported() && (
                <label className="switch">
                  <input type="checkbox" checked={autoRead} onChange={(e) => setAutoRead(e.target.checked)} />
                  <span className="track" />
                  <span className="lbl">음성 자동재생</span>
                </label>
              )}
              <label className="switch">
                <input type="checkbox" checked={isDemo} onChange={(e) => setIsDemo(e.target.checked)} />
                <span className="track" />
                <span className="lbl">데모 모드</span>
              </label>
            </div>
          </div>

          {/* 고객 상황(페르소나) 카드 */}
          <label className="lbl" style={{ display: "block", marginBottom: 8 }}>고객 상황</label>
          <div className="persona-grid">
            {PERSONAS.map((p) => (
              <button
                key={p.value}
                className={`persona-card${persona === p.value ? " on" : ""}`}
                onClick={() => setPersona(p.value)}
                aria-pressed={persona === p.value}
              >
                <Icon name={p.icon} size={20} className="pc-ico" />
                <span className="pc-name">{p.label}</span>
                <span className="pc-desc">{p.desc}</span>
              </button>
            ))}
          </div>

          <button className="btn btn-primary" onClick={newQuestion} disabled={loading} style={{ marginTop: 18, width: "100%" }}>
            <Icon name={questionData ? "refresh" : "send"} size={17} />
            {loading ? "시나리오 생성 중…" : questionData ? "새 시나리오" : "시뮬레이션 시작"}
          </button>
        </div>

        {error && (
          <div className="banner-error" style={{ marginTop: 16 }}>
            <Icon name="shield" size={16} /> {error}
          </div>
        )}

        {/* 시나리오 브리핑 (고객 질문) */}
        {questionData && (
          <div className="card" style={{ marginTop: 16, overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 18px", background: "var(--surface-2)", borderBottom: "1px solid var(--line)" }}>
              <span className="avatar" style={{ borderRadius: 999 }}>
                <Icon name={pc.icon} size={18} />
              </span>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)" }}>{pc.label}</div>
                <div style={{ fontSize: 12, color: "var(--gray-500)" }}>{pc.desc} · 난이도 {DIFFICULTY_LABELS[difficulty]}</div>
              </div>
              <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
                {ttsSupported() && (
                  <button
                    className="btn btn-icon btn-ghost"
                    onClick={() =>
                      speaking
                        ? (cancelSpeak(), setSpeaking(false))
                        : readScenario(questionData.question, activePersona)
                    }
                    aria-label={speaking ? "낭독 중지" : "고객 음성 듣기"}
                    title={speaking ? "낭독 중지" : "고객 음성 듣기"}
                  >
                    <Icon name={speaking ? "stop" : "volume"} size={18} style={speaking ? { color: "var(--orange)" } : undefined} />
                  </button>
                )}
                <span className="chip">
                  <Icon name="chat" size={13} /> 통화 시나리오
                </span>
              </div>
            </div>
            <div style={{ padding: "18px 20px" }}>
              <p style={{ margin: 0, fontSize: 16.5, lineHeight: 1.65, color: "var(--ink)" }}>“{questionData.question}”</p>
              {questionData.reference && (
                <div style={{ marginTop: 12, display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--gray-500)" }}>
                  <Icon name="doc" size={14} /> 편람 위치: {questionData.reference}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 응대 입력 */}
        {questionData && (
          <div style={{ marginTop: 16 }}>
            <label className="lbl" htmlFor="trainee" style={{ display: "block", marginBottom: 8 }}>내 응대</label>
            <textarea
              id="trainee"
              className="field"
              style={{ width: "100%", resize: "vertical", lineHeight: 1.6 }}
              rows={6}
              value={traineeAnswer}
              onChange={(e) => setTraineeAnswer(e.target.value)}
              placeholder="고객에게 응대하듯 답변을 작성하세요…"
            />
            <button className="btn btn-primary" onClick={submit} disabled={submitting} style={{ marginTop: 12 }}>
              <Icon name="check" size={17} />
              {submitting ? "채점 중…" : "응대 제출"}
            </button>
          </div>
        )}

        {/* 스코어카드 */}
        {scoreResult && <ScoreCard result={scoreResult} />}

        {/* 빈 상태 */}
        {!questionData && !loading && (
          <div className="empty" style={{ marginTop: "6vh" }}>
            <span className="badge"><Icon name="coach" size={26} /></span>
            <h2>응대 상황을 훈련해 보세요</h2>
            <p>난이도와 고객 상황을 고르고 "시뮬레이션 시작"을 누르면, AI가 고객이 되어 질문합니다.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function ScoreCard({ result }) {
  const color = result.score >= 80 ? "var(--good)" : result.score >= 60 ? "var(--warn)" : "var(--bad)";
  const criteria = Array.isArray(result.criteria) ? result.criteria : [];
  const tips = Array.isArray(result.coaching_tips) ? result.coaching_tips : [];

  return (
    <div className="card" style={{ padding: 22, marginTop: 20 }}>
      {/* 종합 */}
      <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
        <div className="score-ring" style={{ "--val": result.score }}>
          <span style={{ color }}>
            {result.score}
            <small>/ 100</small>
          </span>
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: "0 0 6px", fontSize: 16, color: "var(--ink)", display: "flex", alignItems: "center", gap: 7 }}>
            <Icon name="trophy" size={17} style={{ color: "var(--orange)" }} /> 채점 결과
          </h3>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "var(--gray-700)" }}>{result.feedback}</p>
        </div>
      </div>

      {/* 루브릭 분해 바 */}
      {criteria.length > 0 && (
        <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 12 }}>
          {criteria.map((c, i) => (
            <div key={i}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5, fontSize: 13 }}>
                <span style={{ color: "var(--gray-700)", fontWeight: 600 }}>
                  {c.name}
                  {c.weight ? <span style={{ color: "var(--gray-400)", fontWeight: 400 }}> · {c.weight}%</span> : null}
                </span>
                <span style={{ color: "var(--gray-500)", fontWeight: 700 }}>{Math.round(c.score ?? 0)}</span>
              </div>
              <div className="bar"><i style={{ width: `${Math.max(0, Math.min(100, c.score ?? 0))}%` }} /></div>
            </div>
          ))}
        </div>
      )}

      {/* 포함 / 누락 */}
      {(result.included_items?.length > 0 || result.missing_items?.length > 0) && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginTop: 16 }}>
          {result.included_items?.map((it, i) => (
            <span key={`o${i}`} className="tag ok"><Icon name="check" size={12} /> {it}</span>
          ))}
          {result.missing_items?.map((it, i) => (
            <span key={`n${i}`} className="tag no"><Icon name="close" size={12} /> {it}</span>
          ))}
        </div>
      )}

      {/* 코칭 — 다음에 적용할 행동 */}
      {tips.length > 0 && (
        <div className="coach-tips">
          <h4><Icon name="bulb" size={15} /> 다음엔 이렇게</h4>
          <ul>
            {tips.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      )}

      {result.reference && (
        <div style={{ marginTop: 14, display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--gray-500)" }}>
          <Icon name="doc" size={14} /> 편람 위치: {result.reference}
        </div>
      )}

      {result.model_answer && (
        <details style={{ marginTop: 14 }}>
          <summary style={{ fontSize: 13.5, color: "var(--orange-700)", cursor: "pointer", fontWeight: 600 }}>모범 답변 보기</summary>
          <div style={{ marginTop: 10, padding: 14, background: "var(--surface-2)", border: "1px solid var(--line)", borderRadius: "var(--r-sm)", fontSize: 14, lineHeight: 1.65, color: "var(--gray-700)", whiteSpace: "pre-wrap" }}>
            {result.model_answer}
          </div>
        </details>
      )}
    </div>
  );
}
