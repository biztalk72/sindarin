"use client";

import Link from "next/link";
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
        <Link className="admin-back" href="/">
          ← workspace
        </Link>
        <h1>Admin · 관찰성</h1>
      </header>

      <section className="admin-card">
        <h2>Health</h2>
        {health && (
          <div className="health-row">
            <span className={`status-badge status-${health.status === "ok" ? "indexed" : "error"}`}>
              {health.status}
            </span>
            {Object.entries(health.components).map(([k, v]) => (
              <span key={k} className="comp">
                {k}: <b className={v === "error" ? "bad" : "good"}>{v}</b>
              </span>
            ))}
          </div>
        )}
      </section>

      <section className="admin-card">
        <h2>Metrics</h2>
        {metrics && (
          <div className="metrics-grid">
            <div><span className="metric-n">{metrics.documents}</span>documents</div>
            <div><span className="metric-n">{metrics.chunks}</span>chunks</div>
            <div><span className="metric-n">{metrics.users}</span>users</div>
            <div><span className="metric-n">{metrics.audit_events}</span>audit events</div>
            <div className="metric-wide">
              jobs: {Object.entries(metrics.ingestion_jobs).map(([s, n]) => `${s}=${n}`).join(", ") || "—"}
            </div>
            <div className="metric-wide">GB10: {metrics.gb10_telemetry}</div>
          </div>
        )}
      </section>

      <section className="admin-card">
        <h2>Ingestion jobs</h2>
        <table className="admin-table">
          <thead>
            <tr><th>document</th><th>stage</th><th>status</th><th>warnings</th></tr>
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
      </section>

      <section className="admin-card">
        <h2>Recent audit</h2>
        <table className="admin-table">
          <thead><tr><th>action</th><th>actor</th><th>when</th></tr></thead>
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
      </section>
    </div>
  );
}
