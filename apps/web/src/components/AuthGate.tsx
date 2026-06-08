"use client";

import Link from "next/link";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { getMe, getToken, login, logout } from "@/lib/api";

type State = "checking" | "out" | "in";

function LoginForm({ onSuccess }: { onSuccess: (role: string) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { role } = await login(email, password);
      onSuccess(role);
    } catch {
      setError("로그인 실패 / login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-center">
      <form className="login" onSubmit={submit}>
        <h1 className="brand">Hybrid IDP</h1>
        <p className="pane-placeholder">로그인 / Sign in</p>
        <input
          type="email"
          aria-label="email"
          placeholder="이메일 / email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
        />
        <input
          type="password"
          aria-label="password"
          placeholder="비밀번호 / password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error && <p className="upload-error">{error}</p>}
        <button type="submit" disabled={busy || !email || !password}>
          {busy ? "…" : "로그인 / Sign in"}
        </button>
      </form>
    </div>
  );
}

export function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>("checking");
  const [role, setRole] = useState("");

  useEffect(() => {
    if (!getToken()) {
      setState("out");
      return;
    }
    getMe()
      .then((me) => {
        setRole(me.role);
        setState("in");
      })
      .catch(() => {
        logout();
        setState("out");
      });
  }, []);

  if (state === "checking") return <div className="auth-center">…</div>;
  if (state === "out") {
    return (
      <LoginForm
        onSuccess={(r) => {
          setRole(r);
          setState("in");
        }}
      />
    );
  }
  return (
    <>
      {children}
      <div className="session-bar">
        {role === "admin" && (
          <Link className="admin-link" href="/admin">
            admin
          </Link>
        )}
        <button
          type="button"
          className="logout-btn"
          onClick={() => {
            logout();
            setState("out");
          }}
        >
          {role} · 로그아웃
        </button>
      </div>
    </>
  );
}
