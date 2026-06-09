"use client";

import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { SessionContext } from "@/components/SessionContext";
import { getMe, getToken, login, logout } from "@/lib/api";

type State = "checking" | "out" | "in";

const EMAIL_KEY = "hidp_email";

function readEmail(): string {
  if (typeof window === "undefined" || !window.localStorage) return "";
  return window.localStorage.getItem(EMAIL_KEY) ?? "";
}
function storeEmail(v: string): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  if (v) window.localStorage.setItem(EMAIL_KEY, v);
  else window.localStorage.removeItem(EMAIL_KEY);
}

function LoginForm({ onSuccess }: { onSuccess: (role: string, email: string) => void }) {
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
      storeEmail(email);
      onSuccess(role, email);
    } catch {
      setError("로그인 실패 / login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-center">
      <form className="login" onSubmit={submit}>
        <div className="login-brand">
          <span className="brand-mark">H</span>
        </div>
        <h1 className="login-title">Hybrid IDP</h1>
        <p className="login-sub">로그인 / Sign in</p>
        <label htmlFor="login-email">이메일 / Email</label>
        <input
          id="login-email"
          type="email"
          aria-label="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
        />
        <label htmlFor="login-password">비밀번호 / Password</label>
        <input
          id="login-password"
          type="password"
          aria-label="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error && <p className="login-error">{error}</p>}
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
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (!getToken()) {
      setState("out");
      return;
    }
    getMe()
      .then((me) => {
        setRole(me.role);
        setEmail(readEmail());
        setState("in");
      })
      .catch(() => {
        logout();
        storeEmail("");
        setState("out");
      });
  }, []);

  if (state === "checking") {
    return <div className="auth-center"><p className="pane-placeholder">…</p></div>;
  }
  if (state === "out") {
    return (
      <LoginForm
        onSuccess={(r, e) => {
          setRole(r);
          setEmail(e);
          setState("in");
        }}
      />
    );
  }
  return (
    <SessionContext.Provider
      value={{
        role,
        email,
        logout: () => {
          logout();
          storeEmail("");
          setRole("");
          setEmail("");
          setState("out");
        },
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}
