import type { Citation } from "@/lib/api";

// UI-CHAT-002: per-answer citation chip — document + page + section, with the source span
// as a tooltip. Clicking jumps to the source preview (UI-CHAT-006 "원문 보기").
export function CitationChip({
  citation,
  index,
  onClick,
}: {
  citation: Citation;
  index: number;
  onClick?: (citation: Citation) => void;
}) {
  const docShort = citation.document_id.slice(0, 8);
  const page = citation.page_no != null ? `p.${citation.page_no}` : "";
  const section = citation.section_path.length ? citation.section_path.join(" › ") : "";
  const label = [`[${index + 1}]`, docShort, page, section].filter(Boolean).join(" · ");
  return (
    <button
      type="button"
      className="citation-chip"
      title={citation.source_span}
      aria-label={`citation ${index + 1} — open source`}
      onClick={() => onClick?.(citation)}
    >
      {label}
    </button>
  );
}
