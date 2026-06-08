import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { AuthGate } from "@/components/AuthGate";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

test("shows login form when no token, then reveals app after login", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ access_token: "tok-123", role: "admin", sub: "u-1" }),
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <AuthGate>
      <div>SECRET WORKSPACE</div>
    </AuthGate>,
  );

  // Protected content is hidden until login.
  expect(screen.queryByText("SECRET WORKSPACE")).not.toBeInTheDocument();

  await userEvent.type(screen.getByLabelText("email"), "admin@example.com");
  await userEvent.type(screen.getByLabelText("password"), "pw");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

  expect(await screen.findByText("SECRET WORKSPACE")).toBeInTheDocument();
  expect(window.localStorage.getItem("hidp_token")).toBe("tok-123");
  expect(fetchMock).toHaveBeenCalledWith("/api/auth/login", expect.objectContaining({ method: "POST" }));
});

test("shows login form when a stored token is rejected (401 on /me)", async () => {
  window.localStorage.setItem("hidp_token", "stale");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ detail: "expired" }) }),
  );

  render(
    <AuthGate>
      <div>SECRET WORKSPACE</div>
    </AuthGate>,
  );

  // Stale token cleared, login form shown.
  expect(await screen.findByLabelText("email")).toBeInTheDocument();
  expect(screen.queryByText("SECRET WORKSPACE")).not.toBeInTheDocument();
  expect(window.localStorage.getItem("hidp_token")).toBeNull();
});
