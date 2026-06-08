"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useSession } from "@/components/SessionContext";

interface Props {
  title: string;
  active: "workspace" | "admin";
  children: ReactNode;
  /** When the page provides its own scroll container (the 3-pane workspace), opt out of body padding/scroll. */
  flush?: boolean;
}

// Shards-Dashboard-React-inspired shell: fixed sidebar (nav + brand) + topbar (title + user) + body.
export function AppShell({ title, active, children, flush = false }: Props) {
  const { role, email, logout } = useSession();
  const isAdmin = role === "admin";

  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="primary navigation">
        <div className="brand">
          <span className="brand-mark">H</span>
          <span>Hybrid IDP</span>
        </div>
        <ul className="nav">
          <li className="nav-section">Workspace</li>
          <li>
            <Link href="/" className={active === "workspace" ? "active" : ""}>
              <span className="nav-icon">▣</span>
              <span>Document AI</span>
            </Link>
          </li>
          {isAdmin && (
            <>
              <li className="nav-section">Operations</li>
              <li>
                <Link href="/admin" className={active === "admin" ? "active" : ""}>
                  <span className="nav-icon">⚙</span>
                  <span>Admin</span>
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
