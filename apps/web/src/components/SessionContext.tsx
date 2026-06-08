"use client";

import { createContext, useContext } from "react";

export interface Session {
  role: string;
  email: string;
  logout: () => void;
}

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession requires <SessionContext.Provider>");
  return ctx;
}
