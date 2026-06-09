"use client";

import {
  IconAlertTriangle,
  IconChartBar,
  IconFileText,
  IconHeartbeat,
  IconHistory,
  IconLayoutDashboard,
  IconReportSearch,
  IconShield,
  IconUserCheck,
} from "@tabler/icons-react";
import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";

import { useSession } from "@/components/SessionContext";
import { type EgressStatus, getEgressStatus } from "@/lib/api";

// Sidebar groups (IA v2):
//   MAIN                  — Workspace, everyone
//   MONITORING            — Health & Metrics, Activity Logs (admin / auditor)
//   GUARDRAILS & POLICY   — Guardrails (read-only), Documents & ACL (read-only) — GP3
//   AUDIT & COMPLIANCE    — Audit Trail (admin / auditor)
export type ShellRoute =
  | "workspace"
  | "health"
  | "logs"
  | "guardrails"
  | "docs-acl"
  | "audit"
  | "dsr"
  | "compliance";

interface Props {
  title: string;
  active: ShellRoute;
  children: ReactNode;
  /** Workspace owns its own scroll; opt out of the body padding. */
  flush?: boolean;
}

function EgressBanner({ status }: { status: EgressStatus }) {
  if (!status.external) return null;
  return (
    <div className="egress-banner" role="alert">
      <IconAlertTriangle size={16} stroke={2} />
      <span>
        <strong>External egress detected.</strong>{" "}
        chat={status.chat.url} {status.chat.in_network ? "(in-net)" : "(external)"} ·{" "}
        embed={status.embed.url} {status.embed.in_network ? "(in-net)" : "(external)"} —
        PRD2 self-hosted invariant violated. Review `.env` model URLs.
      </span>
    </div>
  );
}

export function AppShell({ title, active, children, flush = false }: Props) {
  const { role, email, logout } = useSession();
  const isOps = role === "admin" || role === "auditor";

  const [egress, setEgress] = useState<EgressStatus | null>(null);
  useEffect(() => {
    if (!isOps) return;
    getEgressStatus().then(setEgress).catch(() => setEgress(null));
  }, [isOps]);

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

              <li className="nav-section">GUARDRAILS &amp; POLICY</li>
              <li>
                <Link href="/policy/guardrails" className={active === "guardrails" ? "active" : ""}>
                  <IconShield size={18} stroke={1.75} />
                  <span>Guardrails</span>
                </Link>
              </li>
              <li>
                <Link href="/policy/documents" className={active === "docs-acl" ? "active" : ""}>
                  <IconFileText size={18} stroke={1.75} />
                  <span>Documents &amp; ACL</span>
                </Link>
              </li>

              <li className="nav-section">AUDIT &amp; COMPLIANCE</li>
              <li>
                <Link href="/audit/trail" className={active === "audit" ? "active" : ""}>
                  <IconReportSearch size={18} stroke={1.75} />
                  <span>Audit Trail</span>
                </Link>
              </li>
              <li>
                <Link href="/audit/dsr" className={active === "dsr" ? "active" : ""}>
                  <IconUserCheck size={18} stroke={1.75} />
                  <span>DSR Requests</span>
                </Link>
              </li>
              <li>
                <Link href="/audit/compliance" className={active === "compliance" ? "active" : ""}>
                  <IconChartBar size={18} stroke={1.75} />
                  <span>Compliance Report</span>
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

        {isOps && egress && <EgressBanner status={egress} />}

        {flush ? children : <div className="app-body">{children}</div>}
      </main>
    </div>
  );
}
