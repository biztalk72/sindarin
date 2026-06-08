"use client";

import { useEffect, useState } from "react";

import {
  type AdminHealth,
  type AdminJob,
  type AdminMetrics,
  ApiError,
  type AuditEntry,
  getAdminAudit,
  getAdminHealth,
  getAdminJobs,
  getAdminMetrics,
} from "@/lib/api";

export function AdminDashboard() {
  const [health, setHealth] = useState<AdminHealth | null>(null);
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getAdminHealth(), getAdminMetrics(), getAdminJobs(), getAdminAudit()])
      .then(([h, m, j, a]) => {
        setHealth(h);
        setMetrics(m);
        setJobs(j);
        setAudit(a);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 403) setError("관리자 전용 / admin only");
        else setError(e instanceof Error ? e.message : "failed to load");
      });
  }, []);

  if (error) return <p className="upload-error admin-error">{error}</p>;

  return (
    <div className="admin">
      <header className="admin-head">
        <h1>Operations</h1>
        <span className="admin-sub">Health · Metrics · Jobs · Audit</span>
      </header>

      {metrics && (
        <section className="admin-stats" aria-label="key metrics">
          <div className="stat-card">
            <div className="stat-label">Documents</div>
            <div className="stat-value">{metrics.documents}</div>
            <div className="stat-meta">indexed corpus</div>
          </div>
          <div className="stat-card success">
            <div className="stat-label">Chunks</div>
            <div className="stat-value">{metrics.chunks}</div>
            <div className="stat-meta">retrievable units</div>
          </div>
          <div className="stat-card info">
            <div className="stat-label">Users</div>
            <div className="stat-value">{metrics.users}</div>
            <div className="stat-meta">single-org</div>
          </div>
          <div className="stat-card warning">
            <div className="stat-label">Audit events</div>
            <div className="stat-value">{metrics.audit_events}</div>
            <div className="stat-meta">model + admin actions</div>
          </div>
        </section>
      )}

      <section className="s-card">
        <div className="s-card-header">
          <h2>Health</h2>
          {health && (
            <span className={`status-badge status-${health.status === "ok" ? "indexed" : "error"}`}>
              {health.status}
            </span>
          )}
        </div>
        <div className="s-card-body">
          {health && (
            <div className="health-row">
              {Object.entries(health.components).map(([k, v]) => (
                <span key={k} className="comp">
                  {k}: <b className={v === "error" ? "bad" : "good"}>{v}</b>
                </span>
              ))}
            </div>
          )}
        </div>
      </section>

      {metrics && (
        <section className="s-card">
          <div className="s-card-header"><h2>System</h2></div>
          <div className="s-card-body">
            <div className="metrics-grid">
              <div className="metric-wide">
                <span className="metric-n">
                  {Object.entries(metrics.ingestion_jobs).map(([s, n]) => `${s}=${n}`).join(", ") || "—"}
                </span>
                ingestion jobs
              </div>
              <div className="metric-wide">
                <span className="metric-n">{metrics.gb10_telemetry}</span>
                GB10 telemetry
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="s-card">
        <div className="s-card-header"><h2>Ingestion jobs</h2></div>
        <div className="s-card-body" style={{ padding: 0 }}>
          <table className="admin-table">
            <thead>
              <tr><th>Document</th><th>Stage</th><th>Status</th><th>Warnings</th></tr>
            </thead>
            <tbody>
              {jobs.map((j) => {
                const warnings = (j.metrics?.warnings as string[]) ?? [];
                return (
                  <tr key={j.id}>
                    <td>{j.document_name ?? j.document_id.slice(0, 8)}</td>
                    <td>{j.stage}</td>
                    <td>
                      <span className={`status-badge status-${j.status === "success" ? "indexed" : "error"}`}>
                        {j.status}
                      </span>
                    </td>
                    <td>{warnings.length ? `⚠ ${warnings.length}` : "—"}</td>
                  </tr>
                );
              })}
              {jobs.length === 0 && <tr><td colSpan={4} className="pane-placeholder">no jobs</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="s-card">
        <div className="s-card-header"><h2>Recent audit</h2></div>
        <div className="s-card-body" style={{ padding: 0 }}>
          <table className="admin-table">
            <thead><tr><th>Action</th><th>Actor</th><th>When</th></tr></thead>
            <tbody>
              {audit.map((a, i) => (
                <tr key={i}>
                  <td>{a.action}</td>
                  <td>{a.actor_id ? a.actor_id.slice(0, 8) : "—"}</td>
                  <td>{a.created_at?.replace("T", " ").slice(0, 19) ?? ""}</td>
                </tr>
              ))}
              {audit.length === 0 && <tr><td colSpan={3} className="pane-placeholder">no events</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
