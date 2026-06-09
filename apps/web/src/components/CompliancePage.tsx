"use client";

import { useEffect, useState } from "react";

import { ApiError, type ComplianceSummary, getComplianceSummary } from "@/lib/api";

// /audit/compliance · GP4 D3 — aggregate stats + CSV download. The CSV is fetched via a
// direct `<a>` link (not a typed call) so the browser streams the StreamingResponse to
// disk without buffering in memory.
function fmt(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function CompliancePage() {
  const today = new Date();
  const initFrom = new Date(today);
  initFrom.setDate(initFrom.getDate() - 30);
  const [from, setFrom] = useState<string>(fmt(initFrom));
  const [to, setTo] = useState<string>(fmt(today));
  const [data, setData] = useState<ComplianceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    getComplianceSummary(from, to)
      .then(setData)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 403) setError("관리자 전용 / admin only");
        else setError(e instanceof Error ? e.message : "failed to load");
      });
  }

  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <p className="upload-error admin-error">{error}</p>;

  const csvUrl = `/api/admin/compliance/audit.csv?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;

  return (
    <div className="admin">
      <header className="admin-head">
        <h1>Compliance Report</h1>
        <span className="admin-sub">Aggregate · CSV export · window {from} → {to}</span>
      </header>

      <section className="s-card">
        <div className="s-card-header">
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>
              From&nbsp;
              <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </label>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>
              To&nbsp;
              <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </label>
            <button type="button" className="logout-btn" onClick={load}>Refresh</button>
            <a className="logout-btn" href={csvUrl} download>Download CSV</a>
          </div>
          <span className="admin-sub">{data?.total_events ?? 0} events in window</span>
        </div>
      </section>

      {data && (
        <>
          <section className="admin-stats">
            <div className="stat-card">
              <div className="stat-label">Total events</div>
              <div className="stat-value">{data.total_events}</div>
              <div className="stat-meta">in selected window</div>
            </div>
            <div className="stat-card success">
              <div className="stat-label">Chat cited</div>
              <div className="stat-value">{data.chat.cited_count}</div>
              <div className="stat-meta">claims supported &gt; 0</div>
            </div>
            <div className="stat-card warning">
              <div className="stat-label">Chat dropped</div>
              <div className="stat-value">{data.chat.dropped_count}</div>
              <div className="stat-meta">no claim survived</div>
            </div>
            <div className="stat-card danger">
              <div className="stat-label">Guardrail hits</div>
              <div className="stat-value">
                {data.guardrails_hits_total.input_pii
                  + data.guardrails_hits_total.injection_removed
                  + data.guardrails_hits_total.output_pii}
              </div>
              <div className="stat-meta">PII + injection + output PII</div>
            </div>
          </section>

          <div className="admin-grid-2">
            <section className="s-card">
              <div className="s-card-header"><h2>By kind</h2></div>
              <div className="s-card-body" style={{ padding: 0 }}>
                <table className="admin-table">
                  <thead><tr><th>Kind</th><th>Count</th></tr></thead>
                  <tbody>
                    {Object.entries(data.by_kind).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                      <tr key={k}><td>{k}</td><td>{v}</td></tr>
                    ))}
                    {Object.keys(data.by_kind).length === 0 && (
                      <tr><td colSpan={2} className="pane-placeholder">no events</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="s-card">
              <div className="s-card-header"><h2>By outcome</h2></div>
              <div className="s-card-body" style={{ padding: 0 }}>
                <table className="admin-table">
                  <thead><tr><th>Outcome</th><th>Count</th></tr></thead>
                  <tbody>
                    {Object.entries(data.by_outcome).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                      <tr key={k}><td>{k}</td><td>{v}</td></tr>
                    ))}
                    {Object.keys(data.by_outcome).length === 0 && (
                      <tr><td colSpan={2} className="pane-placeholder">no outcomes recorded yet</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="s-card">
              <div className="s-card-header"><h2>Chat models used</h2></div>
              <div className="s-card-body" style={{ padding: 0 }}>
                <table className="admin-table">
                  <thead><tr><th>Model</th><th>Count</th></tr></thead>
                  <tbody>
                    {Object.entries(data.by_model).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                      <tr key={k}><td style={{ fontFamily: "monospace", fontSize: 12 }}>{k}</td><td>{v}</td></tr>
                    ))}
                    {Object.keys(data.by_model).length === 0 && (
                      <tr><td colSpan={2} className="pane-placeholder">no model labels yet</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="s-card">
              <div className="s-card-header"><h2>Chat latency</h2></div>
              <div className="s-card-body">
                <dl className="quality-grid">
                  <dt>p50</dt><dd>{data.chat.p50_ms != null ? `${data.chat.p50_ms} ms` : "—"}</dd>
                  <dt>p95</dt><dd>{data.chat.p95_ms != null ? `${data.chat.p95_ms} ms` : "—"}</dd>
                  <dt>cited / dropped</dt>
                  <dd>{data.chat.cited_count} / {data.chat.dropped_count}</dd>
                </dl>
              </div>
            </section>
          </div>
        </>
      )}

      <p className="pane-placeholder" style={{ marginTop: 12 }}>
        PDF export (with charts) is a follow-up requiring a heavier dependency
        (reportlab / weasyprint). CSV today is the auditor-friendly machine-readable surface.
      </p>
    </div>
  );
}
