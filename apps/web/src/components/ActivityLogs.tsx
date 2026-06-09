"use client";

import { useEffect, useState } from "react";

import { ApiError, type AuditEntry, getAdminAudit } from "@/lib/api";

// /ops/logs · Activity Logs — last-N audit rows, DB-backed. The daily file viewer
// (GP2) is a separate epic; this page surfaces the same data through the existing
// audit_logs table so admins/auditors can drill into per-call observability today.
const KINDS = ["all", "chat.request"] as const;
const OUTCOMES = ["all", "ok", "dropped", "error"] as const;

export function ActivityLogs() {
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

  if (error) return <p className="upload-error admin-error">{error}</p>;

  return (
    <div className="admin">
      <header className="admin-head">
        <h1>Activity Logs</h1>
        <span className="admin-sub">Recent audit · DB-backed view</span>
      </header>

      <section className="s-card">
        <div className="s-card-header">
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>
              Kind&nbsp;
              <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
                {KINDS.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>
              Outcome&nbsp;
              <select value={outcome} onChange={(e) => setOutcome(e.target.value as typeof outcome)}>
                {OUTCOMES.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </label>
          </div>
          <span className="admin-sub">{rows.length} rows</span>
        </div>
        <div className="s-card-body" style={{ padding: 0 }}>
          <table className="admin-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Kind</th>
                <th>Outcome</th>
                <th>Actor</th>
                <th>Trace</th>
              </tr>
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
      </section>
    </div>
  );
}
