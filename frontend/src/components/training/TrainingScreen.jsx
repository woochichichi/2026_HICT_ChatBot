/**
 * AI 코치 — 응대 상황 시뮬레이션 + 채점 (api-spec.md 섹션 1·11).
 *
 * 연습 방식(체계적 코칭):
 *   - 커리큘럼: 시나리오 뱅크를 난이도(레벨) 순서대로 (런타임 LLM 0, 결정적·반복가능)
 *   - 랜덤    : 뱅크에서 무작위 (실전 감각, LLM 0)
 *   - AI 생성 : LLM(Gemini)이 즉석 출제 (무한 변형, 일일 한도 필요)
 * 뱅크는 주제×페르소나×난이도(level) 메타 + 모범답안·필수항목·출처(source_url)·코칭.
 * 뱅크 채점은 필수항목 커버리지 기반 '규칙 채점'(LLM 0). 진도는 localStorage.
 *
 * 재사용: 페르소나 카드, 시나리오 브리핑, 스코어카드(링/루브릭바/코칭), TTS(lib/tts).
 */

import { useState, useEffect } from "react";
import { fetchQuestion, fetchScore, fetchScenarios } from "../../api/training";
import Icon from "../common/Icon";
import { speak, cancelSpeak, ttsSupported } from "../../lib/tts";

const DIFFICULTIES = [
  { value: "beginner", label: "초급", level: 1 },
  { value: "intermediate", label: "중급", level: 2 },
  { value: "advanced", label: "고급", level: 3 },
];
const DIFF_LABEL = Object.fromEntries(DIFFICULTIES.map((d) => [d.value, d.label]));
const DIFF_LEVEL = Object.fromEntries(DIFFICULTIES.map((d) => [d.value, d.level]));

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

const MODES = [
  { value: "curriculum", label: "커리큘럼" },
  // { value: "random", label: "랜덤" },  // 임시 숨김 — 채점 점검 중. 출제/채점 로직(next 213번)은 유지
  { value: "review", label: "복습" },
  { value: "ai", label: "AI 생성" },
];
const REVIEW_THRESHOLD = 80; // 최고점이 이 미만이면 '미숙련' → 복습 대상

const PROGRESS_KEY = "aicoach_progress_v1";
const loadProgress = () => {
  try {
    return JSON.parse(localStorage.getItem(PROGRESS_KEY) || "{}");
  } catch {
    return {};
  }
};
const saveProgress = (p) => {
  try {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(p));
  } catch {
    /* noop */
  }
};

const norm = (s) => (s || "").replace(/\s+/g, "");

// 뱅크 채점(규칙 기반, LLM 0): 필수항목 커버리지
function ruleScore(scenario, answer) {
  const req = scenario.required_items || [];
  const a = norm(answer);
  const included = req.filter((k) => a.includes(norm(k)));
  const missing = req.filter((k) => !a.includes(norm(k)));
  const score = req.length ? Math.round((included.length / req.length) * 100) : 0;
  const feedback =
    `필수 항목 ${included.length}/${req.length}개를 포함했습니다.` +
    (missing.length ? ` 누락: ${missing.join(", ")}.` : " 핵심 요소를 잘 짚었습니다.");
  return {
    score,
    criteria: [{ name: "필수 항목 포함", score, weight: 100 }],
    coaching_tips: scenario.coaching_tips || [],
    included_items: included,
    missing_items: missing,
    feedback,
    reference: scenario.reference || "",
    source_url: scenario.source_url || "",
    model_answer: scenario.model_answer || "",
  };
}

export default function TrainingScreen() {
  const [mode, setMode] = useState("curriculum");
  const [difficulty, setDifficulty] = useState("beginner");
  const [persona, setPersona] = useState("standard");
  const [scenarios, setScenarios] = useState([]);
  const [bankPos, setBankPos] = useState(0); // 커리큘럼 진행 위치
  const [questionData, setQuestionData] = useState(null);
  const [activeScenario, setActiveScenario] = useState(null); // 뱅크 채점용
  const [solvedContentIds, setSolvedContentIds] = useState([]);
  const [traineeAnswer, setTraineeAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [scoreResult, setScoreResult] = useState(null);
  const [activePersona, setActivePersona] = useState("standard");
  const [history, setHistory] = useState([]);
  const [autoRead, setAutoRead] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [progress, setProgress] = useState(loadProgress);

  useEffect(() => {
    fetchScenarios().then(setScenarios).catch(() => setScenarios([]));
    return () => cancelSpeak();
  }, []);

  const readScenario = (text, personaKey) => {
    setSpeaking(true);
    speak(text, {
      ...(PERSONA_VOICE[personaKey] || PERSONA_VOICE.standard),
      persona: personaKey,
      onstart: () => setSpeaking(true),
      onend: () => setSpeaking(false),
    });
  };

  // 현재 난이도/페르소나에 맞는 뱅크 풀
  const poolFor = () => {
    const lvl = DIFF_LEVEL[difficulty];
    let pool = scenarios.filter((s) => s.level === lvl);
    const byP = pool.filter((s) => s.persona === persona);
    if (byP.length) pool = byP; // 페르소나 필터(비면 난이도만)
    if (!pool.length) pool = scenarios.filter((s) => s.level === lvl);
    if (!pool.length) pool = scenarios;
    return pool;
  };

  // 오답(미숙련) 시나리오 — 최고점 < 임계값, 약한 것부터 (복습 우선순위)
  const wrongScenarios = () =>
    scenarios
      .filter((s) => progress[s.id] && progress[s.id].best < REVIEW_THRESHOLD)
      .sort((a, b) => progress[a.id].best - progress[b.id].best);

  const serveScenario = (sc, posLabel) => {
    setActiveScenario(sc);
    setActivePersona(sc.persona || "standard");
    setQuestionData({
      question: sc.question,
      reference: sc.reference || "",
      source_url: sc.source_url || "",
      _posLabel: posLabel,
    });
    if (autoRead) readScenario(sc.question, sc.persona || "standard");
  };

  const next = async () => {
    cancelSpeak();
    setSpeaking(false);
    setError(null);
    setTraineeAnswer("");
    setScoreResult(null);

    if (mode === "ai") {
      // LLM 즉석 출제(기존 경로)
      setLoading(true);
      setQuestionData(null);
      setActiveScenario(null);
      try {
        const data = await fetchQuestion({ difficulty, solvedContentIds, isDemo: false, persona });
        setActivePersona(persona);
        setQuestionData({ question: data.question, reference: data.reference, source_url: data.source_url || "", question_id: data.question_id });
        if (autoRead) readScenario(data.question, persona);
        setSolvedContentIds((prev) =>
          data.is_reset ? [data.source_content_id] : [...prev, data.source_content_id].filter(Boolean)
        );
      } catch (err) {
        setError(err.message || "질문을 불러오지 못했습니다(LLM 한도일 수 있습니다 — 커리큘럼/랜덤은 항상 동작).");
      } finally {
        setLoading(false);
      }
      return;
    }

    // 복습 — 약점(미숙련)부터 출제
    if (mode === "review") {
      const wrong = wrongScenarios();
      if (!wrong.length) {
        setError("복습할 오답이 없습니다. 커리큘럼/랜덤으로 먼저 연습해 보세요.");
        return;
      }
      serveScenario(wrong[0], `약점 복습 (${wrong.length}건 남음)`);
      return;
    }

    // 뱅크(커리큘럼/랜덤) — LLM 0
    const pool = poolFor();
    if (!pool.length) {
      setError("해당 난이도의 시나리오가 없습니다.");
      return;
    }
    if (mode === "curriculum") {
      const pos = bankPos % pool.length;
      serveScenario(pool[pos], `${pos + 1}/${pool.length}`);
      setBankPos(pos + 1);
    } else {
      const i = Math.floor(Math.random() * pool.length);
      serveScenario(pool[i], null);
    }
  };

  const submit = async () => {
    if (!questionData || !traineeAnswer.trim()) {
      setError("답변을 입력해 주세요.");
      return;
    }
    setError(null);
    if (activeScenario) {
      // 규칙 채점(LLM 0)
      const result = ruleScore(activeScenario, traineeAnswer.trim());
      setScoreResult(result);
      setHistory((h) => [...h, result.score]);
      // 진도 저장
      const id = activeScenario.id;
      setProgress((prev) => {
        const cur = prev[id] || { best: 0, attempts: 0 };
        const upd = {
          best: Math.max(cur.best, result.score),
          attempts: cur.attempts + 1,
          last: result.score,
          missing: result.missing_items || [],
          at: Date.now(),
        };
        const np = { ...prev, [id]: upd };
        saveProgress(np);
        return np;
      });
      return;
    }
    // AI 모드 — LLM 채점
    setSubmitting(true);
    setScoreResult(null);
    try {
      const result = await fetchScore({ questionId: questionData.question_id, traineeAnswer: traineeAnswer.trim(), persona: activePersona });
      setScoreResult(result);
      setHistory((h) => [...h, result.score]);
    } catch (err) {
      setError(err.message || "채점에 실패했습니다(LLM 한도일 수 있습니다).");
    } finally {
      setSubmitting(false);
    }
  };

  const avg = history.length ? Math.round(history.reduce((a, b) => a + b, 0) / history.length) : null;
  const pc = PERSONA_MAP[activePersona] || PERSONAS[0];
  const bankCount = scenarios.filter((s) => s.level === DIFF_LEVEL[difficulty]).length;
  const doneCount = Object.values(progress).filter((v) => v.attempts > 0).length;

  return (
    <div className="content">
      <div className="content-pad" style={{ maxWidth: 820 }}>
        {/* 설정 */}
        <div className="card" style={{ padding: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
            <h2 style={{ margin: 0, fontSize: 15, color: "var(--ink)", display: "flex", alignItems: "center", gap: 7 }}>
              <Icon name="target" size={17} style={{ color: "var(--orange)" }} /> 시나리오 설정
            </h2>
            <div className="progress-strip">
              <div><div className="pv">{doneCount}</div><div className="pl">학습한 시나리오</div></div>
              <div><div className="pv">{avg ?? "–"}{avg != null && <span style={{ fontSize: 12, color: "var(--gray-400)" }}> 점</span>}</div><div className="pl">세션 평균</div></div>
            </div>
          </div>

          {/* 연습 방식 */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
            <label className="lbl" style={{ minWidth: 64 }}>연습 방식</label>
            <div className="seg">
              {MODES.map((m) => (
                <button key={m.value} className={mode === m.value ? "on" : ""} onClick={() => { setMode(m.value); setBankPos(0); }}>
                  {m.label}
                </button>
              ))}
            </div>
            {mode === "ai" && (
              <span className="chip" style={{ color: "var(--warn)", background: "var(--warn-bg)", borderColor: "#fed7aa" }}>
                LLM 사용(일일 한도)
              </span>
            )}
            {ttsSupported() && (
              <label className="switch" style={{ marginLeft: "auto" }}>
                <input type="checkbox" checked={autoRead} onChange={(e) => setAutoRead(e.target.checked)} />
                <span className="track" />
                <span className="lbl">음성 자동재생</span>
              </label>
            )}
          </div>

          {/* 복습 모드: 오답 노트 / 그 외: 난이도+고객상황 */}
          {mode === "review" ? (
            <ReviewNote scenarios={scenarios} progress={progress} onRetry={(sc) => serveScenario(sc, "오답 다시 풀기")} />
          ) : (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
                <label className="lbl" style={{ minWidth: 64 }}>난이도</label>
                <div className="seg">
                  {DIFFICULTIES.map((d) => (
                    <button key={d.value} className={difficulty === d.value ? "on" : ""} onClick={() => { setDifficulty(d.value); setBankPos(0); }}>
                      {d.label}
                    </button>
                  ))}
                </div>
                {mode !== "ai" && (
                  <span style={{ fontSize: 12, color: "var(--gray-400)" }}>이 난이도 시나리오 {bankCount}개</span>
                )}
              </div>

              <label className="lbl" style={{ display: "block", marginBottom: 8 }}>
                고객 상황 {mode !== "ai" && <span style={{ color: "var(--gray-400)", fontWeight: 400 }}>(해당 상황 시나리오 우선)</span>}
              </label>
              <div className="persona-grid">
                {PERSONAS.map((p) => (
                  <button key={p.value} className={`persona-card${persona === p.value ? " on" : ""}`} onClick={() => { setPersona(p.value); setBankPos(0); }} aria-pressed={persona === p.value}>
                    <Icon name={p.icon} size={20} className="pc-ico" />
                    <span className="pc-name">{p.label}</span>
                    <span className="pc-desc">{p.desc}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          <button className="btn btn-primary" onClick={next} disabled={loading} style={{ marginTop: 18, width: "100%" }}>
            <Icon name={questionData ? "refresh" : "send"} size={17} />
            {loading
              ? "시나리오 생성 중…"
              : mode === "review"
                ? (questionData ? "다음 오답" : "약점부터 복습 시작")
                : (questionData ? "다음 시나리오" : "시뮬레이션 시작")}
          </button>
        </div>

        {error && (
          <div className="banner-error" style={{ marginTop: 16 }}>
            <Icon name="shield" size={16} /> {error}
          </div>
        )}

        {/* 시나리오 브리핑 */}
        {questionData && (
          <div className="card" style={{ marginTop: 16, overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 18px", background: "var(--surface-2)", borderBottom: "1px solid var(--line)" }}>
              <span className="avatar" style={{ borderRadius: 999 }}><Icon name={pc.icon} size={18} /></span>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)" }}>{pc.label}</div>
                <div style={{ fontSize: 12, color: "var(--gray-500)" }}>{pc.desc} · 난이도 {DIFF_LABEL[difficulty]}{questionData._posLabel ? ` · ${questionData._posLabel}` : ""}</div>
              </div>
              <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
                {ttsSupported() && (
                  <button className="btn btn-icon btn-ghost" onClick={() => (speaking ? (cancelSpeak(), setSpeaking(false)) : readScenario(questionData.question, activePersona))} aria-label={speaking ? "낭독 중지" : "고객 음성 듣기"} title={speaking ? "낭독 중지" : "고객 음성 듣기"}>
                    <Icon name={speaking ? "stop" : "volume"} size={18} style={speaking ? { color: "var(--orange)" } : undefined} />
                  </button>
                )}
                <span className="chip"><Icon name="chat" size={13} /> 통화 시나리오</span>
              </div>
            </div>
            <div style={{ padding: "18px 20px" }}>
              <p style={{ margin: 0, fontSize: 16.5, lineHeight: 1.65, color: "var(--ink)" }}>“{questionData.question}”</p>
              <SourceLine reference={questionData.reference} url={questionData.source_url} />
            </div>
          </div>
        )}

        {/* 응대 입력 */}
        {questionData && (
          <div style={{ marginTop: 16 }}>
            <label className="lbl" htmlFor="trainee" style={{ display: "block", marginBottom: 8 }}>내 응대</label>
            <textarea id="trainee" className="field" style={{ width: "100%", resize: "vertical", lineHeight: 1.6 }} rows={6}
              value={traineeAnswer} onChange={(e) => setTraineeAnswer(e.target.value)} placeholder="고객에게 응대하듯 답변을 작성하세요…" />
            <button className="btn btn-primary" onClick={submit} disabled={submitting} style={{ marginTop: 12 }}>
              <Icon name="check" size={17} />
              {submitting ? "채점 중…" : "응대 제출"}
            </button>
          </div>
        )}

        {scoreResult && <ScoreCard result={scoreResult} />}

        {!questionData && !loading && (
          <div className="empty" style={{ marginTop: "6vh" }}>
            <span className="badge"><Icon name="coach" size={26} /></span>
            <h2>응대 상황을 훈련해 보세요</h2>
            <p>커리큘럼 순서로 난이도·상황별 시나리오를 연습하고, 응대를 채점받으세요. (커리큘럼·랜덤은 LLM 없이 동작)</p>
          </div>
        )}
      </div>
    </div>
  );
}

// 오답 노트 — 최고점 < 임계값 시나리오를 약한 순으로. '다시 풀기'로 재출제.
function ReviewNote({ scenarios, progress, onRetry }) {
  const wrong = scenarios
    .filter((s) => progress[s.id] && progress[s.id].best < REVIEW_THRESHOLD)
    .sort((a, b) => progress[a.id].best - progress[b.id].best);
  const mastered = scenarios.filter((s) => progress[s.id] && progress[s.id].best >= REVIEW_THRESHOLD).length;

  if (!wrong.length) {
    return (
      <div style={{ padding: "18px 0", textAlign: "center", color: "var(--gray-500)" }}>
        <Icon name="trophy" size={24} style={{ color: "var(--orange)" }} />
        <p style={{ margin: "8px 0 0", fontSize: 14 }}>
          복습할 오답이 없습니다. {mastered > 0 ? `숙련 ${mastered}개 — 잘하고 있어요!` : "커리큘럼/랜덤으로 먼저 연습해 보세요."}
        </p>
      </div>
    );
  }
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <label className="lbl">오답 노트 <span style={{ color: "var(--gray-400)", fontWeight: 400 }}>(80점 미만 · 약한 순)</span></label>
        <span style={{ fontSize: 12, color: "var(--gray-400)" }}>{wrong.length}건 · 숙련 {mastered}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 320, overflowY: "auto" }}>
        {wrong.map((s) => {
          const pr = progress[s.id];
          const pcl = PERSONA_MAP[s.persona]?.label || s.persona;
          return (
            <div key={s.id} style={{ border: "1px solid var(--line)", borderLeft: "4px solid var(--bad)", borderRadius: "var(--r-sm)", padding: "10px 12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
                <span className="tag no">{pr.best}점</span>
                <span style={{ fontSize: 12, color: "var(--gray-500)" }}>{s.category} · L{s.level} · {pcl}</span>
                <button className="btn btn-sm" style={{ marginLeft: "auto" }} onClick={() => onRetry(s)}>
                  <Icon name="refresh" size={14} /> 다시 풀기
                </button>
              </div>
              <div style={{ fontSize: 13.5, color: "var(--ink)", lineHeight: 1.5 }}>{s.question}</div>
              {pr.missing?.length > 0 && (
                <div style={{ marginTop: 6, fontSize: 12, color: "var(--bad)" }}>누락했던 항목: {pr.missing.join(", ")}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SourceLine({ reference, url }) {
  if (!reference && !url) return null;
  const label = reference || "편람 출처";
  return (
    <div style={{ marginTop: 12, display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--gray-500)" }}>
      <Icon name="doc" size={14} /> 편람 위치:{" "}
      {url ? (
        <a href={url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--orange-700)", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4 }}>
          {label} <Icon name="external" size={13} />
        </a>
      ) : (
        <span>{label}</span>
      )}
    </div>
  );
}

function ScoreCard({ result }) {
  const color = result.score >= 80 ? "var(--good)" : result.score >= 60 ? "var(--warn)" : "var(--bad)";
  const criteria = Array.isArray(result.criteria) ? result.criteria : [];
  const tips = Array.isArray(result.coaching_tips) ? result.coaching_tips : [];

  return (
    <div className="card" style={{ padding: 22, marginTop: 20 }}>
      <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
        <div className="score-ring" style={{ "--val": result.score }}>
          <span style={{ color }}>{result.score}<small>/ 100</small></span>
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ margin: "0 0 6px", fontSize: 16, color: "var(--ink)", display: "flex", alignItems: "center", gap: 7 }}>
            <Icon name="trophy" size={17} style={{ color: "var(--orange)" }} /> 채점 결과
          </h3>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "var(--gray-700)" }}>{result.feedback}</p>
        </div>
      </div>

      {criteria.length > 0 && (
        <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 12 }}>
          {criteria.map((c, i) => (
            <div key={i}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5, fontSize: 13 }}>
                <span style={{ color: "var(--gray-700)", fontWeight: 600 }}>
                  {c.name}{c.weight ? <span style={{ color: "var(--gray-400)", fontWeight: 400 }}> · {c.weight}%</span> : null}
                </span>
                <span style={{ color: "var(--gray-500)", fontWeight: 700 }}>{Math.round(c.score ?? 0)}</span>
              </div>
              <div className="bar"><i style={{ width: `${Math.max(0, Math.min(100, c.score ?? 0))}%` }} /></div>
            </div>
          ))}
        </div>
      )}

      {(result.included_items?.length > 0 || result.missing_items?.length > 0) && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginTop: 16 }}>
          {result.included_items?.map((it, i) => <span key={`o${i}`} className="tag ok"><Icon name="check" size={12} /> {it}</span>)}
          {result.missing_items?.map((it, i) => <span key={`n${i}`} className="tag no"><Icon name="close" size={12} /> {it}</span>)}
        </div>
      )}

      {tips.length > 0 && (
        <div className="coach-tips">
          <h4><Icon name="bulb" size={15} /> 다음엔 이렇게</h4>
          <ul>{tips.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}

      <SourceLine reference={result.reference} url={result.source_url} />

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
