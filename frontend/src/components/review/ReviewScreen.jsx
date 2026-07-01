/**
 * 제보 검토 (운영) — 오답 제보 누적 목록 조회 + 처리완료 (api-spec.md 섹션 11).
 * 데이터 선순환: 제보 → 축적 → 검토 → 편람/답변 보정.
 *
 * 스타일: index.css(.card/.seg/.chip/.tag/.btn). 아이콘: Icon.jsx. API: api/feedback.js.
 */

import { useState, useEffect, useCallback } from "react";
import { listFeedback, resolveFeedback } from "../../api/feedback";
import Icon from "../common/Icon";
import Markdown from "../common/Markdown";
import { CONFIDENCE_STYLE } from "../../theme";

const FILTERS = [
  { key: "open", label: "미처리" },
  { key: "resolved", label: "처리완료" },
  { key: "", label: "전체" },
];

const fmt = (s) => (s || "").replace("T", " ").replace(/(\+.*|Z)$/, "");

export default function ReviewScreen() {
  const [filter, setFilter] = useState("open");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFeedback(filter || undefined);
      setItems(data.items || []);
    } catch (err) {
      setError(err.message || "목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const resolve = async (id) => {
    setBusyId(id);
    setError(null);
    try {
      await resolveFeedback(id);
      await load();
    } catch (err) {
      setError(err.message || "처리에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="content">
      <div className="content-pad">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
          <div className="seg">
            {FILTERS.map((f) => (
              <button key={f.key || "all"} className={filter === f.key ? "on" : ""} onClick={() => setFilter(f.key)}>
                {f.label}
              </button>
            ))}
          </div>
          <button className="btn btn-sm" onClick={load}>
            <Icon name="refresh" size={15} /> 새로고침
          </button>
        </div>

        {error && (
          <div className="banner-error" style={{ marginBottom: 14 }}>
            <Icon name="shield" size={16} /> {error}
          </div>
        )}

        {loading && <p style={{ color: "var(--gray-400)", fontSize: 14 }}>불러오는 중…</p>}

        {!loading && items.length === 0 && (
          <div className="empty" style={{ marginTop: "8vh" }}>
            <span className="badge"><Icon name="inbox" size={26} /></span>
            <h2>{filter === "open" ? "미처리 제보가 없습니다" : "제보가 없습니다"}</h2>
            <p>응대 모드에서 답변에 '오답 제보'를 하면 여기에 쌓입니다.</p>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((it) => (
            <ReviewCard key={it.id} item={it} busy={busyId === it.id} onResolve={() => resolve(it.id)} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ReviewCard({ item, busy, onResolve }) {
  const conf = CONFIDENCE_STYLE[item.confidence] ? item.confidence : null;
  const resolved = item.status === "resolved";

  return (
    <div className="card" style={{ padding: 16, borderLeft: `4px solid ${resolved ? "var(--gray-400)" : "var(--orange)"}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <span
          className="tag"
          style={resolved
            ? { color: "var(--gray-600)", background: "var(--line-2)" }
            : { color: "var(--orange-700)", background: "var(--orange-50)" }}
        >
          {resolved ? <Icon name="check" size={12} /> : <Icon name="flag" size={12} />}
          {resolved ? "처리완료" : "미처리"}
        </span>
        <span style={{ fontSize: 12, color: "var(--gray-400)" }}>#{item.id}</span>
        <span style={{ fontSize: 12, color: "var(--gray-400)" }}>{fmt(item.created_at)} UTC</span>
        {conf && (
          <span className={`chip conf-${conf}`}>
            <Icon name="shield" size={12} /> 신뢰도 {CONFIDENCE_STYLE[conf].label}
          </span>
        )}
      </div>

      <Field label="질문" value={item.question} />
      {/* AI 답변 — 마크다운 렌더(raw 노출 방지) */}
      <div style={{ marginBottom: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: "var(--gray-400)" }}>AI 답변</span>
        <div style={{ marginTop: 2, color: "var(--gray-700)", fontSize: 14 }}>
          <Markdown content={item.answer} />
        </div>
      </div>
      <Field label="제보 사유" value={item.reason} tone="bad" />
      {item.suggested && <Field label="정답 제안" value={item.suggested} tone="good" />}

      {Array.isArray(item.sources) && item.sources.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--gray-500)" }}>
          출처: {item.sources.map((s, i) => (i ? ", " : "") + (s.title || "(제목없음)")).join("")}
        </div>
      )}

      {!resolved ? (
        <div style={{ marginTop: 12, textAlign: "right" }}>
          <button className="btn btn-primary btn-sm" onClick={onResolve} disabled={busy}>
            {busy ? "처리 중…" : <><Icon name="check" size={15} /> 처리완료</>}
          </button>
        </div>
      ) : (
        item.resolved_at && (
          <p style={{ margin: "10px 0 0", fontSize: 12, color: "var(--gray-400)", textAlign: "right" }}>
            처리: {fmt(item.resolved_at)} UTC
          </p>
        )
      )}
    </div>
  );
}

function Field({ label, value, muted, tone }) {
  const color = tone === "bad" ? "var(--bad)" : tone === "good" ? "var(--good)" : muted ? "var(--gray-500)" : "var(--ink)";
  return (
    <div style={{ marginBottom: 6 }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: "var(--gray-400)", marginRight: 6 }}>{label}</span>
      <span style={{ fontSize: 14, lineHeight: 1.6, color, whiteSpace: "pre-wrap" }}>{value}</span>
    </div>
  );
}
