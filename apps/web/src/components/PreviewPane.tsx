"use client";

import { useEffect, useRef, useState } from "react";

import { type DocumentPreview, getPreview, type PreviewBlock, type PreviewTarget } from "@/lib/api";

// A block is highlighted when its text is part of the cited source span (citation jump), or
// when it belongs to the targeted section/page (TOC jump).
function isHighlighted(block: PreviewBlock, target: PreviewTarget): boolean {
  if (target.span && block.text.trim()) {
    return target.span.includes(block.text.trim());
  }
  if (target.title && block.section_path.includes(target.title)) return true;
  if (target.page_no != null && block.page_no === target.page_no) return true;
  return false;
}

export function PreviewPane({
  target,
  onClose,
}: {
  target: PreviewTarget;
  onClose: () => void;
}) {
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const firstHit = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setPreview(null);
    setError(null);
    getPreview(target.documentId)
      .then((p) => !cancelled && setPreview(p))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "failed"));
    return () => {
      cancelled = true;
    };
  }, [target.documentId]);

  useEffect(() => {
    if (preview) firstHit.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [preview]);

  let seenHit = false;
  let lastPage: number | null = null;

  return (
    <div className="preview" role="dialog" aria-label="document preview">
      <div className="preview-header">
        <button type="button" className="preview-close" onClick={onClose}>
          ← 채팅 / Back
        </button>
        <span className="preview-title">{preview?.name ?? "…"}</span>
      </div>

      <div className="preview-body">
        {error && <p className="upload-error">{error}</p>}
        {!preview && !error && <p className="pane-placeholder">불러오는 중… / loading…</p>}
        {preview?.blocks.length === 0 && (
          <p className="pane-placeholder">미리보기 내용 없음 / no preview content</p>
        )}
        {preview?.blocks.map((b, i) => {
          const hit = isHighlighted(b, target);
          const ref = hit && !seenHit ? firstHit : undefined;
          if (hit) seenHit = true;
          const showPage = b.page_no != null && b.page_no !== lastPage;
          lastPage = b.page_no ?? lastPage;
          return (
            <div key={`${b.block_ref}-${i}`}>
              {showPage && <div className="preview-page-sep">— p.{b.page_no} —</div>}
              <div
                ref={ref}
                className={`preview-block block-${b.block_type}${hit ? " highlight" : ""}`}
              >
                {b.text}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
