"use client";

import { useCallback, useEffect, useState } from "react";

import { useSession } from "@/components/SessionContext";
import {
  ApiError,
  createDsr,
  type DsrRow,
  getAdminDsr,
  getMyDsr,
  processDsr,
} from "@/lib/api";

// /audit/dsr · Data-Subject Requests (GP4 D2)
//
// Two roles share this page:
//   - any authenticated user: see their own requests + open a new export/forget request
//   - admin/auditor: see EVERY request in a separate card; admin can mark them processed
export function DsrPage() {
  const { role } = useSession();
  const isAdmin = role === "admin";
  const isAuditor = role === "auditor";

  const [mine, setMine] = useState<DsrRow[]>([]);
  const [all, setAll] = useState<DsrRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const me = await getMyDsr();
      setMine(me);
      if (isAdmin || isAuditor) setAll(await getAdminDsr());
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load");
    }
  }, [isAdmin, isAuditor]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function onCreate(kind: "export" | "forget") {
    if (kind === "forget" && !confirm(
      "Forget는 이 사용자의 audit log를 익명화하고 계정을 tombstone 처리합니다. 진행할까요?"
    )) return;
    setBusy(true);
    try { await createDsr(kind); await refresh(); }
    catch (e) { setError(e instanceof ApiError ? e.message : (e instanceof Error ? e.message : "create failed")); }
    finally { setBusy(false); }
  }

  async function onProcess(id: string) {
    setBusy(true);
    try { await processDsr(id); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "process failed"); }
    finally { setBusy(false); }
  }

  function StatusBadge({ s }: { s: DsrRow["status"] }) {
    const cls = s === "completed" ? "indexed" : s === "rejected" ? "error" : "uploaded";
    return <span className={`status-badge status-${cls}`}>{s}</span>;
  }

  return (
    <div className="admin">
      <header className="admin-head">
        <h1>Data Subject Requests</h1>
        <span className="admin-sub">Export · Forget · processing trail</span>
      </header>

      {error && <p className="upload-error">{error}</p>}

      <section className="s-card">
        <div className="s-card-header">
          <h2>내 요청 / My requests</h2>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="logout-btn" disabled={busy} onClick={() => onCreate("export")}>
              + Export
            </button>
            <button type="button" className="logout-btn" disabled={busy} onClick={() => onCreate("forget")}>
              + Forget
            </button>
          </div>
        </div>
        <div className="s-card-body" style={{ padding: 0 }}>
          <table className="admin-table">
            <thead><tr><th>Kind</th><th>Status</th><th>Created</th><th>Processed</th><th>Result</th></tr></thead>
            <tbody>
              {mine.map((r) => (
                <tr key={r.id}>
                  <td>{r.kind}</td>
                  <td><StatusBadge s={r.status} /></td>
                  <td>{r.created_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                  <td>{r.processed_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 11, maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {r.result ? JSON.stringify(r.result) : "—"}
                  </td>
                </tr>
              ))}
              {mine.length === 0 && (
                <tr><td colSpan={5} className="pane-placeholder">no requests yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {(isAdmin || isAuditor) && (
        <section className="s-card">
          <div className="s-card-header">
            <h2>전체 요청 / All requests</h2>
            <span className="admin-sub">admin · auditor</span>
          </div>
          <div className="s-card-body" style={{ padding: 0 }}>
            <table className="admin-table">
              <thead><tr><th>Requester</th><th>Kind</th><th>Status</th><th>Created</th><th>Result</th><th></th></tr></thead>
              <tbody>
                {all.map((r) => (
                  <tr key={r.id}>
                    <td style={{ fontFamily: "monospace", fontSize: 11 }}>{r.requester_id.slice(0, 8)}</td>
                    <td>{r.kind}</td>
                    <td><StatusBadge s={r.status} /></td>
                    <td>{r.created_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 11, maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {r.result ? JSON.stringify(r.result) : "—"}
                    </td>
                    <td>
                      {isAdmin && r.status === "pending" && (
                        <button type="button" className="logout-btn" disabled={busy} onClick={() => onProcess(r.id)}>
                          Process
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {all.length === 0 && (
                  <tr><td colSpan={6} className="pane-placeholder">no requests</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <p className="pane-placeholder" style={{ marginTop: 12 }}>
        Forget 처리는 audit log actor 익명화 + 사용자 tombstone + ACL drop만 적용합니다.
        문서/벡터 인덱스 정리는 retention worker(GP3-retention)의 범위입니다.
      </p>
    </div>
  );
}
