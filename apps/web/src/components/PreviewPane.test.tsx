import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { PreviewPane } from "@/components/PreviewPane";

const PREVIEW = {
  document_id: "d1",
  name: "contract.html",
  type: "html",
  blocks: [
    { block_ref: "b1", page_no: 1, block_type: "heading", text: "계약 조건", section_path: ["계약 조건"] },
    {
      block_ref: "b2",
      page_no: 1,
      block_type: "paragraph",
      text: "위약금은 100만원이다.",
      section_path: ["계약 조건"],
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

test("renders source blocks and highlights the cited span", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => PREVIEW }));
  render(<PreviewPane target={{ documentId: "d1", span: "위약금은 100만원이다." }} onClose={vi.fn()} />);

  const cited = await screen.findByText("위약금은 100만원이다.");
  expect(cited).toHaveClass("highlight");
  // the heading is not part of the cited span → not highlighted
  expect(screen.getByText("계약 조건")).not.toHaveClass("highlight");
});

test("highlights by section title for a TOC jump", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => PREVIEW }));
  render(<PreviewPane target={{ documentId: "d1", title: "계약 조건" }} onClose={vi.fn()} />);

  expect(await screen.findByText("계약 조건")).toHaveClass("highlight");
});
