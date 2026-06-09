"use client";

import { useEffect, useState } from "react";

import { ApiError, type DocumentCard, listDocuments } from "@/lib/api";

const LEVEL_LABEL: Record<string, string> = {
  public: "공개",
  internal: "내부",
  confidential: "기밀",
  restricted: "비공개",
};

// /policy/documents · Documents & ACL — GP3 read-only listing of documents with
// classification + owner. Per-document classification edit + ACL editor land in a follow-up
// GP3 PR (this PR is read-only to keep scope contained).
export function DocumentsAclPage() {
  const [docs, setDocs] = useState<DocumentCard[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [levelFilter, setLevelFilter] = useState<string>("all");

  useEffect(() => {
    listDocuments()
      .then(setDocs)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 403) setError("관리자 전용 / admin only");
        else setError(e instanceof Error ? e.message : "failed to load");
      });
  }, []);

  if (error) return <p className="upload-error admin-error">{error}</p>;

  const filtered = levelFilter === "all" ? docs : docs.filter((d) => d.security_level === levelFilter);
  const counts: Record<string, number> = {};
  for (const d of docs) counts[d.security_level] = (counts[d.security_level] ?? 0) + 1;

  return (
    <div className="admin">
      <header className="admin-head">
        <h1>Documents &amp; ACL</h1>
        <span className="admin-sub">Classification · owner · retention</span>
      </header>

      <section className="admin-stats">
        {(["public", "internal", "confidential", "restricted"] as const).map((lvl) => (
          <div key={lvl} className={`stat-card ${lvl === "restricted" ? "danger" : lvl === "confidential" ? "warning" : lvl === "internal" ? "" : "info"}`}>
            <div className="stat-label">{LEVEL_LABEL[lvl]}</div>
            <div className="stat-value">{counts[lvl] ?? 0}</div>
            <div className="stat-meta">{lvl}</div>
          </div>
        ))}
      </section>

      <section className="s-card">
        <div className="s-card-header">
          <label style={{ fontSize: 12, color: "var(--muted)" }}>
            Level&nbsp;
            <select value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)}>
              <option value="all">all</option>
              <option value="public">public</option>
              <option value="internal">internal</option>
              <option value="confidential">confidential</option>
              <option value="restricted">restricted</option>
            </select>
          </label>
          <span className="admin-sub">{filtered.length} of {docs.length}</span>
        </div>
        <div className="s-card-body" style={{ padding: 0 }}>
          <table className="admin-table">
            <thead>
              <tr><th>Document</th><th>Type</th><th>Classification</th><th>Status</th><th>Chunks</th><th>Created</th></tr>
            </thead>
            <tbody>
              {filtered.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.type}</td>
                  <td>
                    <span className={`level-badge level-${d.security_level}`}>
                      {LEVEL_LABEL[d.security_level] ?? d.security_level}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge status-${d.status}`}>{d.status}</span>
                  </td>
                  <td>{d.chunk_count}</td>
                  <td>{d.created_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={6} className="pane-placeholder">no documents</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <p className="pane-placeholder" style={{ marginTop: 12 }}>
        Per-document Classification edit + ACL editor + lineage drill-down land in the GP3 edit PR.
      </p>
    </div>
  );
}
