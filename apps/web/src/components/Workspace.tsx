"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import ChatWorkspace from "@/components/ChatWorkspace";
import { DocumentLibrary } from "@/components/DocumentLibrary";
import { InsightPanel } from "@/components/InsightPanel";
import { PreviewPane } from "@/components/PreviewPane";
import { type DocumentCard, listDocuments, type PreviewTarget } from "@/lib/api";

// 3-pane document AI workspace (PRD2 §8.1). Owns the shared document list + selection so the
// library (left) scopes the chat (center). Insight pane (right) is a placeholder (E10).
export default function Workspace() {
  const [documents, setDocuments] = useState<DocumentCard[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<PreviewTarget | null>(null);

  const refresh = useCallback(() => {
    listDocuments()
      .then(setDocuments)
      .catch(() => setDocuments([]));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const toggle = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <AppShell title="Document AI workspace" active="workspace" flush>
      <div className="workspace">
        <aside className="pane left" aria-label="document library">
          <DocumentLibrary
            documents={documents}
            selected={selected}
            onToggle={toggle}
            onChanged={refresh}
          />
        </aside>

        <section className="pane center" aria-label="chat workspace">
          <ChatWorkspace scopeDocumentIds={[...selected]} onOpenPreview={setPreview} />
          {preview && <PreviewPane target={preview} onClose={() => setPreview(null)} />}
        </section>

        <aside className="pane right" aria-label="document insight">
          <InsightPanel
            documentId={selected.size === 1 ? [...selected][0] : null}
            document={
              selected.size === 1
                ? documents.find((d) => d.id === [...selected][0]) ?? null
                : null
            }
            onOpenPreview={setPreview}
          />
        </aside>
      </div>
    </AppShell>
  );
}
