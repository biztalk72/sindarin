import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import { InsightPanel } from "@/components/InsightPanel";

function mockApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const json = url.endsWith("/toc")
        ? { toc_tree: [{ title: "계약", page_no: 1, children: [{ title: "위약금", page_no: 2, children: [] }] }] }
        : url.endsWith("/keywords")
          ? { keywords: [{ keyword: "위약금", weight: 1.0, kind: null }] }
          : url.endsWith("/quality")
            ? {
                document_id: "d1",
                name: "c.docx",
                type: "docx",
                security_level: "internal",
                status: "success",
                metrics: { parser: "markitdown", extraction_coverage: 1.0, blocks: 3, chunks: 2, warnings: [] },
              }
            : { nodes: [{ id: "위약금", label: "위약금" }], edges: [] };
      return Promise.resolve({ ok: true, json: async () => json });
    }),
  );
}

afterEach(() => vi.restoreAllMocks());

test("prompts to select a document when none chosen", () => {
  render(<InsightPanel documentId={null} />);
  expect(screen.getByText(/Select one document/)).toBeInTheDocument();
});

test("renders TOC tree then switches to keywords", async () => {
  mockApi();
  render(<InsightPanel documentId="d1" />);

  expect(await screen.findByText("계약")).toBeInTheDocument();
  expect(screen.getByText("위약금")).toBeInTheDocument(); // nested child
  expect(screen.getByText("p.2")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("tab", { name: "키워드" }));
  // TOC unmounts; the keyword cloud renders 위약금 from the keywords endpoint.
  expect(await screen.findByText("위약금")).toBeInTheDocument();
  expect(screen.queryByText("계약")).not.toBeInTheDocument();
});

test("quality tab shows parser + coverage + reprocess", async () => {
  mockApi();
  render(<InsightPanel documentId="d1" />);
  await userEvent.click(screen.getByRole("tab", { name: "품질" }));

  expect(await screen.findByText("markitdown")).toBeInTheDocument();
  expect(screen.getByText("100%")).toBeInTheDocument(); // extraction coverage
  expect(screen.getByRole("button", { name: /reprocess/i })).toBeDisabled();
});
