"use client";

import { type FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  createOverride,
  type GuardrailEvent,
  type GuardrailOverride,
  type GuardrailPolicies,
  getGuardrailEvents,
  getGuardrailPolicies,
  getOverrides,
  revokeOverride,
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

      <OverridesSection policies={pols} />

      <p className="pane-placeholder" style={{ marginTop: 12 }}>
        DB-backed policies + per-policy enable/disable + override-applied-at-runtime land in
        GP4 D1b (this page records intent today — runtime apply is the follow-up).
      </p>
    </div>
  );
}

function OverridesSection({ policies }: { policies: GuardrailPolicies | null }) {
  const [rows, setRows] = useState<GuardrailOverride[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [kind, setKind] = useState<"pii" | "injection">("pii");
  const [policyName, setPolicyName] = useState<string>("");
  const [reason, setReason] = useState<string>("");
  const [ttl, setTtl] = useState<number>(60);

  const refresh = () =>
    getOverrides(false)
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "failed to load overrides"));

  useEffect(() => { refresh(); }, []);

  const piiNames = policies?.pii.map((p) => p.name) ?? [];
  const injNames = (policies?.injection ?? []).map((_, i) => `injection-${i + 1}`);
  const choices = kind === "pii" ? piiNames : injNames;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await createOverride({ kind, policy_name: policyName, reason, ttl_minutes: ttl });
      setReason("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err instanceof Error ? err.message : "create failed"));
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(id: string) {
    setError(null);
    try {
      await revokeOverride(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "revoke failed");
    }
  }

  return (
    <section className="s-card">
      <div className="s-card-header">
        <h2>Overrides</h2>
        <span className="admin-sub">audit-only — runtime apply lands in D1b</span>
      </div>
      <div className="s-card-body">
        {error && <p className="upload-error" style={{ marginTop: 0 }}>{error}</p>}

        <form onSubmit={onSubmit} style={{ display: "grid", gridTemplateColumns: "auto 1fr auto auto", gap: 10, alignItems: "center" }}>
          <select value={kind} onChange={(e) => { setKind(e.target.value as "pii" | "injection"); setPolicyName(""); }}>
            <option value="pii">PII</option>
            <option value="injection">Injection</option>
          </select>
          <select value={policyName} onChange={(e) => setPolicyName(e.target.value)} required>
            <option value="">— pick a policy —</option>
            {choices.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <input
            type="number"
            min={1}
            max={1440}
            value={ttl}
            onChange={(e) => setTtl(parseInt(e.target.value || "60", 10))}
            style={{ width: 80, padding: 6 }}
            aria-label="ttl minutes"
            title="TTL (minutes, 1–1440)"
          />
          <button type="submit" disabled={busy || !policyName || reason.length < 8}>
            {busy ? "…" : "+ Override"}
          </button>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="reason (min 8 chars) — describe why this bypass is justified"
            rows={2}
            style={{ gridColumn: "1 / -1", padding: 8, fontFamily: "inherit", fontSize: 13 }}
            required
            minLength={8}
          />
        </form>

        <table className="admin-table" style={{ marginTop: 16 }}>
          <thead>
            <tr><th>Kind</th><th>Policy</th><th>Reason</th><th>Active</th><th>Created</th><th>Expires</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.id}>
                <td>{o.kind}</td>
                <td>{o.policy_name}</td>
                <td style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis" }} title={o.reason}>{o.reason}</td>
                <td>
                  <span className={`status-badge status-${o.active ? "indexed" : "error"}`}>
                    {o.active ? "active" : (o.revoked_at ? "revoked" : "expired")}
                  </span>
                </td>
                <td>{o.created_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                <td>{o.expires_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                <td>
                  {o.active && (
                    <button type="button" className="logout-btn" onClick={() => onRevoke(o.id)}>
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={7} className="pane-placeholder">no overrides — happy path</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
