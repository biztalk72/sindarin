import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import ChatWorkspace from "@/components/ChatWorkspace";

const CITED_RESPONSE = {
  answer: "위약금은 100만원이다.",
  citations: [
    {
      document_id: "0e14c485-4d4f-479e-80c7-64b0fd0dc04d",
      chunk_id: "c1",
      page_no: 1,
      section_path: ["계약", "위약금"],
      source_span: "계약 해지 시 위약금은 100만원으로 한다.",
    },
  ],
  confidence: { groundedness: 1.0, citation_coverage: 1.0, retrieval_quality: 0.42 },
  warnings: [],
  retrieval_trace_id: "trace-1",
};

afterEach(() => {
  vi.restoreAllMocks();
});

test("sends a question and renders a cited, grounded answer", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => CITED_RESPONSE,
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<ChatWorkspace />);
  await userEvent.type(screen.getByRole("textbox"), "위약금 얼마");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));

  // The answer renders.
  expect(await screen.findByText("위약금은 100만원이다.")).toBeInTheDocument();
  // Citation chip carries page + section path (unique to the chip label).
  expect(screen.getByText(/p\.1 · 계약 › 위약금/)).toBeInTheDocument();
  // Confidence badge.
  expect(screen.getByText(/groundedness 100%/)).toBeInTheDocument();

  // Posted to the proxied endpoint with the message.
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/chat", expect.anything()));
  const body = JSON.parse(fetchMock.mock.calls[0][1].body);
  expect(body.message).toBe("위약금 얼마");
});

test("clicking a citation chip opens the source preview", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => CITED_RESPONSE }));
  const onOpenPreview = vi.fn();
  render(<ChatWorkspace onOpenPreview={onOpenPreview} />);

  await userEvent.type(screen.getByRole("textbox"), "위약금");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  await screen.findByText("위약금은 100만원이다.");

  await userEvent.click(screen.getByRole("button", { name: /citation 1 — open source/i }));
  expect(onOpenPreview).toHaveBeenCalledWith(
    expect.objectContaining({
      documentId: CITED_RESPONSE.citations[0].document_id,
      span: CITED_RESPONSE.citations[0].source_span,
    }),
  );
});

test("shows the server error detail when the API returns 503", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: "no documents ingested yet" }),
    }),
  );

  render(<ChatWorkspace />);
  await userEvent.type(screen.getByRole("textbox"), "hi");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));

  expect(await screen.findByText(/no documents ingested yet/)).toBeInTheDocument();
});
