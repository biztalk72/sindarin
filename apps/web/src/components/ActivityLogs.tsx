"use client";

import { useEffect, useState } from "react";

import {
  ApiError,
  type AuditEntry,
  getAdminAudit,
  getLogByDate,
  getLogDates,
  type LogEvent,
} from "@/lib/api";

// /ops/logs · Activity Logs — two sources:
//  - DB tab (audit_logs): up-to-the-second source of truth; filterable by kind/outcome.
//  - File tab (events-YYYY-MM-DD.jsonl, GP2): overlap-window daily files for forensic dumps.
const KINDS = ["all", "chat.request"] as const;
const OUTCOMES = ["all", "ok", "dropped", "error"] as const;
type Source = "db" | "file";

function pickDate(ev: LogEvent): string {
  return (ev.ts_local || ev.ts || "").replace("T", " ").slice(0, 19);
}

function DbTab() {
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [kind, setKind] = useState<(typeof KINDS)[number]>("all");
  const [outcome, setOutcome] = useState<(typeof OUTCOMES)[number]>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    getAdminAudit({
      limit: 100,
      kind: kind === "all" ? undefined : kind,
      outcome: outcome === "all" ? undefined : outcome,
    })
      .then(setRows)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 403) setError("관리자 전용 / admin only");
        else setError(e instanceof Error ? e.message : "failed to load");
      });
  }, [kind, outcome]);

  if (error) return <p className="upload-error">{error}</p>;
  return (
    <>
      <div className="s-card-header">
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <label style={{ fontSize: 12, color: "var(--muted)" }}>
            Kind&nbsp;
            <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
              {KINDS.map((k) => (<option key={k} value={k}>{k}</option>))}
            </select>
          </label>
          <label style={{ fontSize: 12, color: "var(--muted)" }}>
            Outcome&nbsp;
            <select value={outcome} onChange={(e) => setOutcome(e.target.value as typeof outcome)}>
              {OUTCOMES.map((o) => (<option key={o} value={o}>{o}</option>))}
            </select>
          </label>
        </div>
        <span className="admin-sub">{rows.length} rows</span>
      </div>
      <div className="s-card-body" style={{ padding: 0 }}>
        <table className="admin-table">
          <thead>
            <tr><th>When</th><th>Kind</th><th>Outcome</th><th>Actor</th><th>Trace</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.event_id ?? `${i}-${r.created_at}`}>
                <td>{r.created_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                <td>{r.kind ?? r.action}</td>
                <td>
                  <span className={`status-badge status-${r.outcome === "ok" ? "indexed" : "error"}`}>
                    {r.outcome ?? "—"}
                  </span>
                </td>
                <td>{r.actor_id ? r.actor_id.slice(0, 8) : "—"}</td>
                <td style={{ fontFamily: "monospace", fontSize: 11 }}>
                  {r.trace_id ? r.trace_id.slice(0, 12) : "—"}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={5} className="pane-placeholder">no events match the filter</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function FileTab() {
  const [dates, setDates] = useState<string[]>([]);
  const [date, setDate] = useState<string>("");
  const [rows, setRows] = useState<LogEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLogDates()
      .then((d) => { setDates(d); if (d.length > 0) setDate((cur) => cur || d[0]); })
      .catch((e) => setError(e instanceof Error ? e.message : "failed to load dates"));
  }, []);

  useEffect(() => {
    if (!date) return;
    setError(null);
    getLogByDate(date)
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "failed to load file"));
  }, [date]);

  if (error) return <p className="upload-error">{error}</p>;
  return (
    <>
      <div className="s-card-header">
        <label style={{ fontSize: 12, color: "var(--muted)" }}>
          Date&nbsp;
          <select value={date} onChange={(e) => setDate(e.target.value)} disabled={dates.length === 0}>
            {dates.length === 0 && <option>(no files yet)</option>}
            {dates.map((d) => (<option key={d} value={d}>{d}</option>))}
          </select>
        </label>
        <span className="admin-sub">{rows.length} lines (overlap window {date ? date : "—"})</span>
      </div>
      <div className="s-card-body" style={{ padding: 0 }}>
        <table className="admin-table">
          <thead>
            <tr><th>When (local)</th><th>Kind</th><th>Outcome</th><th>Actor</th><th>Duration</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const dur = (r.metrics?.duration_ms as number | undefined) ?? null;
              return (
                <tr key={r.event_id ?? `${i}-${r.ts}`}>
                  <td>{pickDate(r)}</td>
                  <td>{r.kind ?? "—"}</td>
                  <td>
                    <span className={`status-badge status-${r.outcome === "ok" ? "indexed" : "error"}`}>
                      {r.outcome ?? "—"}
                    </span>
                  </td>
                  <td>{r.actor?.user_id ? r.actor.user_id.slice(0, 8) : "—"}</td>
                  <td>{dur != null ? `${dur} ms` : "—"}</td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={5} className="pane-placeholder">file is empty or missing</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function ActivityLogs() {
  const [source, setSource] = useState<Source>("db");
  return (
    <div className="admin">
      <header className="admin-head">
        <h1>Activity Logs</h1>
        <span className="admin-sub">Source-of-record + daily overlap files</span>
      </header>

      <div className="insight-tabs" role="tablist" style={{ marginBottom: 12 }}>
        {(["db", "file"] as Source[]).map((s) => (
          <button
            key={s}
            type="button"
            role="tab"
            aria-selected={source === s}
            className={`insight-tab${source === s ? " active" : ""}`}
            onClick={() => setSource(s)}
          >
            {s === "db" ? "DB (audit_logs)" : "File (events-YYYY-MM-DD.jsonl)"}
          </button>
        ))}
      </div>

      <section className="s-card">{source === "db" ? <DbTab /> : <FileTab />}</section>
    </div>
  );
}
