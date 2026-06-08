import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { AdminDashboard } from "@/components/AdminDashboard";

afterEach(() => vi.restoreAllMocks());

function mockAdminApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const body = url.endsWith("/health")
        ? { status: "ok", components: { postgres: "ok", vector_db: "ok", model_endpoint: "dev-mode" } }
        : url.endsWith("/metrics")
          ? {
              documents: 7,
              chunks: 12,
              users: 1,
              audit_events: 3,
              ingestion_jobs: { success: 7 },
              host: { cpu_count: 8 },
              gb10_telemetry: "unavailable (collect on the GB10 node)",
            }
          : url.endsWith("/jobs")
            ? [{ id: "j1", document_id: "d1", document_name: "contract.docx", stage: "indexed", status: "success", metrics: { warnings: [] }, created_at: "2026-06-08T00:00:00" }]
            : [{ action: "chat", actor_id: "u-1", payload_hash: "abc", created_at: "2026-06-08T00:00:00" }];
      return Promise.resolve({ ok: true, json: async () => body });
    }),
  );
}

test("renders health, metrics, jobs and audit", async () => {
  mockAdminApi();
  render(<AdminDashboard />);

  expect(await screen.findByText("7")).toBeInTheDocument(); // documents metric
  expect(screen.getByText("contract.docx")).toBeInTheDocument(); // job row
  expect(screen.getByText("postgres:")).toBeInTheDocument(); // health component label
  expect(screen.getByText("dev-mode")).toBeInTheDocument(); // model_endpoint status (unique)
});

test("shows admin-only message on 403", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({ detail: "requires role" }) }),
  );
  render(<AdminDashboard />);
  expect(await screen.findByText(/admin only/)).toBeInTheDocument();
});
