"use client";

import {
  IconHeartbeat,
  IconHistory,
  IconLayoutDashboard,
  IconReportSearch,
} from "@tabler/icons-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { useSession } from "@/components/SessionContext";

// Sidebar groups (PRD2 §8.1 IA + IA-v2 grouping):
//   MAIN            — Workspace, everyone
//   MONITORING      — Health & Metrics, Activity Logs (admin / auditor)
//   AUDIT & COMPLIANCE — Audit Trail (admin / auditor)
// GUARDRAILS & POLICY group lands in GP3; not rendered in GP1 to avoid an empty header.
export type ShellRoute = "workspace" | "health" | "logs" | "audit";

interface Props {
  title: string;
  active: ShellRoute;
  children: ReactNode;
  /** Workspace owns its own scroll; opt out of the body padding. */
  flush?: boolean;
}

export function AppShell({ title, active, children, flush = false }: Props) {
  const { role, email, logout } = useSession();
  const isOps = role === "admin" || role === "auditor";

  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="primary navigation">
        <div className="brand">
          <span className="brand-mark">H</span>
          <span>Hybrid IDP</span>
        </div>
        <ul className="nav">
          <li>
            <Link href="/" className={active === "workspace" ? "active" : ""}>
              <IconLayoutDashboard size={18} stroke={1.75} />
              <span>Document AI</span>
            </Link>
          </li>

          {isOps && (
            <>
              <li className="nav-section">MONITORING</li>
              <li>
                <Link href="/ops/health" className={active === "health" ? "active" : ""}>
                  <IconHeartbeat size={18} stroke={1.75} />
                  <span>Health &amp; Metrics</span>
                </Link>
              </li>
              <li>
                <Link href="/ops/logs" className={active === "logs" ? "active" : ""}>
                  <IconHistory size={18} stroke={1.75} />
                  <span>Activity Logs</span>
                </Link>
              </li>

              <li className="nav-section">AUDIT &amp; COMPLIANCE</li>
              <li>
                <Link href="/audit/trail" className={active === "audit" ? "active" : ""}>
                  <IconReportSearch size={18} stroke={1.75} />
                  <span>Audit Trail</span>
                </Link>
              </li>
            </>
          )}
        </ul>
      </aside>

      <main className="app-main">
        <header className="app-topbar">
          <h1 className="page-title">{title}</h1>
          <div className="topbar-right">
            <div className="user-chip">
              <span>{email || "user"}</span>
              <span className="role">{role}</span>
            </div>
            <button type="button" className="logout-btn" onClick={logout}>
              로그아웃
            </button>
          </div>
        </header>

        {flush ? children : <div className="app-body">{children}</div>}
      </main>
    </div>
  );
}
