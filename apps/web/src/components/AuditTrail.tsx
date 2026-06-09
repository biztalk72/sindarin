"use client";

import { useEffect, useState } from "react";

import { ApiError, type AuditEntry, getAdminAudit } from "@/lib/api";

// /audit/trail · Audit Trail — same data as Activity Logs but a row-expand view that
// surfaces the GP1 metrics blob (duration, model, groundedness, guardrails, warnings).
// This is the primary screen auditors use.
function MetricsBlock({ metrics }: { metrics: Record<string, unknown> }) {
  const entries = Object.entries(metrics);
  if (entries.length === 0) return <span className="pane-placeholder">no metrics</span>;
  return (
    <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12 }}>
      {entries.map(([k, v]) => (
        <li key={k}>
          <strong style={{ color: "var(--muted)" }}>{k}:</strong>{" "}
          {typeof v === "object" ? JSON.stringify(v) : String(v)}
        </li>
      ))}
    </ul>
  );
}

export function AuditTrail() {
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    getAdminAudit({ limit: 200 })
      .then(setRows)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 403) setError("관리자 전용 / admin only");
        else setError(e instanceof Error ? e.message : "failed to load");
      });
  }, []);

  if (error) return <p className="upload-error admin-error">{error}</p>;

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="admin">
      <header className="admin-head">
        <h1>Audit Trail</h1>
        <span className="admin-sub">Per-event observability · click a row to expand</span>
      </header>

      <section className="s-card">
        <div className="s-card-header"><h2>Recent events ({rows.length})</h2></div>
        <div className="s-card-body" style={{ padding: 0 }}>
          <table className="admin-table">
            <thead>
              <tr>
                <th></th>
                <th>When</th>
                <th>Kind</th>
                <th>Outcome</th>
                <th>Actor</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const id = r.event_id ?? `${i}-${r.created_at}`;
                const isOpen = expanded.has(id);
                const dur = (r.metrics?.duration_ms as number | undefined) ?? null;
                return (
                  <>
                    <tr key={id} onClick={() => toggle(id)} style={{ cursor: "pointer" }}>
                      <td style={{ width: 16 }}>{isOpen ? "▼" : "▶"}</td>
                      <td>{r.created_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                      <td>{r.kind ?? r.action}</td>
                      <td>
                        <span className={`status-badge status-${r.outcome === "ok" ? "indexed" : "error"}`}>
                          {r.outcome ?? "—"}
                        </span>
                      </td>
                      <td>{r.actor_id ? r.actor_id.slice(0, 8) : "—"}</td>
                      <td>{dur != null ? `${dur} ms` : "—"}</td>
                    </tr>
                    {isOpen && (
                      <tr key={`${id}-detail`}>
                        <td colSpan={6} style={{ background: "var(--bg)" }}>
                          <div style={{ padding: "8px 16px" }}>
                            {r.trace_id && (
                              <div style={{ fontSize: 12 }}>
                                <strong style={{ color: "var(--muted)" }}>trace:</strong>{" "}
                                <code style={{ fontSize: 11 }}>{r.trace_id}</code>
                              </div>
                            )}
                            <MetricsBlock metrics={r.metrics ?? {}} />
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
              {rows.length === 0 && (
                <tr><td colSpan={6} className="pane-placeholder">no events</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
