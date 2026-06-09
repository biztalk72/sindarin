"use client";

import { useEffect, useState } from "react";

import {
  ApiError,
  type GuardrailEvent,
  type GuardrailPolicies,
  getGuardrailEvents,
  getGuardrailPolicies,
} from "@/lib/api";

// /policy/guardrails · GP3 read-only. Two cards: active patterns (code-loaded) and
// recent activity (projected from audit_logs.metrics.guardrails). Edit + override land in GP4.
export function GuardrailsPage() {
  const [pols, setPols] = useState<GuardrailPolicies | null>(null);
  const [events, setEvents] = useState<GuardrailEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getGuardrailPolicies(), getGuardrailEvents()])
      .then(([p, e]) => { setPols(p); setEvents(e); })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 403) setError("관리자 전용 / admin only");
        else setError(e instanceof Error ? e.message : "failed to load");
      });
  }, []);

  if (error) return <p className="upload-error admin-error">{error}</p>;

  const totalHits = events.reduce(
    (acc, e) => acc + e.input_pii + e.injection_removed + e.output_pii,
    0,
  );

  return (
    <div className="admin">
      <header className="admin-head">
        <h1>Guardrails</h1>
        <span className="admin-sub">PII · Injection · runtime audit</span>
      </header>

      <section className="admin-stats" aria-label="guardrail counts">
        <div className="stat-card">
          <div className="stat-label">PII patterns</div>
          <div className="stat-value">{pols?.pii.length ?? 0}</div>
          <div className="stat-meta">code-loaded (GP4: DB)</div>
        </div>
        <div className="stat-card info">
          <div className="stat-label">Injection patterns</div>
          <div className="stat-value">{pols?.injection.length ?? 0}</div>
          <div className="stat-meta">EN + KO regex</div>
        </div>
        <div className="stat-card warning">
          <div className="stat-label">Events (recent)</div>
          <div className="stat-value">{events.length}</div>
          <div className="stat-meta">chat with hits &gt; 0</div>
        </div>
        <div className="stat-card danger">
          <div className="stat-label">Hits (recent)</div>
          <div className="stat-value">{totalHits}</div>
          <div className="stat-meta">PII + injection + output PII</div>
        </div>
      </section>

      <section className="s-card">
        <div className="s-card-header"><h2>PII patterns</h2></div>
        <div className="s-card-body" style={{ padding: 0 }}>
          <table className="admin-table">
            <thead><tr><th>Name</th><th>Regex</th></tr></thead>
            <tbody>
              {(pols?.pii ?? []).map((p) => (
                <tr key={p.name}>
                  <td>{p.name}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 11 }}>{p.pattern}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="s-card">
        <div className="s-card-header"><h2>Injection patterns</h2></div>
        <div className="s-card-body" style={{ padding: 0 }}>
          <table className="admin-table">
            <thead><tr><th>#</th><th>Regex</th></tr></thead>
            <tbody>
              {(pols?.injection ?? []).map((p, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 11 }}>{p.pattern}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="s-card">
        <div className="s-card-header"><h2>Recent events (chat with hits)</h2></div>
        <div className="s-card-body" style={{ padding: 0 }}>
          <table className="admin-table">
            <thead>
              <tr>
                <th>When</th><th>Trace</th><th>PII (in)</th><th>Injection</th><th>PII (out)</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={e.event_id ?? `${i}-${e.created_at}`}>
                  <td>{e.created_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 11 }}>
                    {e.trace_id ? e.trace_id.slice(0, 12) : "—"}
                  </td>
                  <td>{e.input_pii || "—"}</td>
                  <td>{e.injection_removed || "—"}</td>
                  <td>{e.output_pii || "—"}</td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr><td colSpan={5} className="pane-placeholder">no guardrail activity in the recent window</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <p className="pane-placeholder" style={{ marginTop: 12 }}>
        Override workflow + DB-backed policies + per-policy enable/disable land in GP4.
      </p>
    </div>
  );
}
