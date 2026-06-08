import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { DocumentLibrary } from "@/components/DocumentLibrary";
import type { DocumentCard } from "@/lib/api";

const DOCS: DocumentCard[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    name: "contract.docx",
    type: "docx",
    status: "indexed",
    security_level: "internal",
    created_at: "2026-06-05T00:00:00",
    chunk_count: 3,
  },
];

afterEach(() => vi.restoreAllMocks());

test("renders document cards with status badge and chunk count", () => {
  render(<DocumentLibrary documents={DOCS} selected={new Set()} onToggle={vi.fn()} onChanged={vi.fn()} />);
  expect(screen.getByText("contract.docx")).toBeInTheDocument();
  expect(screen.getByText("색인 완료")).toBeInTheDocument(); // indexed
  expect(screen.getByText("3 chunks")).toBeInTheDocument();
});

test("toggles selection on checkbox click", async () => {
  const onToggle = vi.fn();
  render(<DocumentLibrary documents={DOCS} selected={new Set()} onToggle={onToggle} onChanged={vi.fn()} />);
  await userEvent.click(screen.getByRole("checkbox", { name: /select contract.docx/i }));
  expect(onToggle).toHaveBeenCalledWith(DOCS[0].id);
});

test("uploads a file and triggers refresh", async () => {
  const onChanged = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({ document_id: "d2", chunks: 1 }) }),
  );
  render(<DocumentLibrary documents={[]} selected={new Set()} onToggle={vi.fn()} onChanged={onChanged} />);

  const input = screen.getByLabelText("upload documents") as HTMLInputElement;
  await userEvent.upload(input, new File(["a,b\n1,2\n"], "data.csv", { type: "text/csv" }));

  await waitFor(() => expect(onChanged).toHaveBeenCalled());
  expect(fetch).toHaveBeenCalledWith("/api/upload", expect.objectContaining({ method: "POST" }));
});
