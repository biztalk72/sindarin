"use client";

import { useEffect, useState } from "react";

import { ForceGraph } from "@/components/ForceGraph";
import {
  type DocumentCard,
  type DocumentQuality,
  type GraphData,
  getGraph,
  getKeywords,
  getQuality,
  getToc,
  type KeywordItem,
  type PreviewTarget,
  type TocNode,
} from "@/lib/api";

type Tab = "toc" | "keywords" | "graph" | "quality" | "access";

const LEVEL_LABEL: Record<string, string> = {
  public: "공개",
  internal: "내부",
  confidential: "기밀",
  restricted: "비공개",
};

function AccessPanel({ document }: { document: DocumentCard | null }) {
  if (!document) return <p className="pane-placeholder">문서 메타 없음 / no metadata</p>;
  return (
    <div className="access">
      <dl className="quality-grid">
        <dt>이름 / name</dt><dd>{document.name}</dd>
        <dt>유형 / type</dt><dd>{document.type}</dd>
        <dt>분류 / classification</dt>
        <dd>
          <span className={`level-badge level-${document.security_level}`}>
            {LEVEL_LABEL[document.security_level] ?? document.security_level}
          </span>
        </dd>
        <dt>상태 / status</dt>
        <dd>
          <span className={`status-badge status-${document.status}`}>{document.status}</span>
        </dd>
        <dt>등록 / created</dt><dd>{document.created_at?.replace("T", " ").slice(0, 19) ?? "—"}</dd>
        <dt>청크 수 / chunks</dt><dd>{document.chunk_count}</dd>
      </dl>
      <p className="pane-placeholder" style={{ marginTop: 12 }}>
        Owner / ACL / lineage / retention 편집은 GP3에서 활성화됩니다 — read-only.
      </p>
    </div>
  );
}

function pct(v: number | null | undefined): string {
  return typeof v === "number" ? `${Math.round(v * 100)}%` : "—";
}

function QualityPanel({ quality }: { quality: DocumentQuality | null }) {
  if (!quality) return <p className="pane-placeholder">품질 정보 없음 / no quality data</p>;
  const m = quality.metrics;
  const warnings = m.warnings ?? [];
  return (
    <div className="quality">
      <dl className="quality-grid">
        <dt>parser</dt><dd>{m.parser ?? "—"}</dd>
        <dt>status</dt>
        <dd>
          <span className={`status-badge status-${quality.status === "success" ? "indexed" : "error"}`}>
            {quality.status}
          </span>
        </dd>
        <dt>extraction</dt><dd>{pct(m.extraction_coverage)}</dd>
        <dt>OCR confidence</dt><dd>{pct(m.ocr_confidence)}</dd>
        <dt>blocks / chunks</dt><dd>{m.blocks ?? "—"} / {m.chunks ?? "—"}</dd>
        <dt>security</dt><dd>{quality.security_level}</dd>
      </dl>
      <div className="quality-warnings">
        {warnings.length ? (
          warnings.map((w) => (
            <div key={w} className="warning-badge">⚠ {w}</div>
          ))
        ) : (
          <span className="pane-placeholder">경고 없음 / no warnings</span>
        )}
      </div>
      <button type="button" className="reprocess-btn" disabled title="reprocess (E6 retry — soon)">
        재처리 / Reprocess (soon)
      </button>
    </div>
  );
}

function TocTree({ nodes, onJump }: { nodes: TocNode[]; onJump?: (n: TocNode) => void }) {
  if (nodes.length === 0) return <p className="pane-placeholder">목차 없음 / no headings</p>;
  return (
    <ul className="toc-tree">
      {nodes.map((n, i) => (
        <li key={`${n.title}-${i}`}>
          <button type="button" className="toc-title" onClick={() => onJump?.(n)}>
            {n.title}
          </button>
          {n.page_no != null && <span className="toc-page">p.{n.page_no}</span>}
          {n.children.length > 0 && <TocTree nodes={n.children} onJump={onJump} />}
        </li>
      ))}
    </ul>
  );
}

function KeywordCloud({ keywords }: { keywords: KeywordItem[] }) {
  if (keywords.length === 0) return <p className="pane-placeholder">키워드 없음 / no keywords</p>;
  return (
    <div className="cloud">
      {keywords.map((k) => {
        const w = k.weight ?? 0.5;
        const size = 12 + Math.round(w * 14); // 12–26px by weight
        return (
          <span key={k.keyword} className="cloud-word" style={{ fontSize: size }} title={k.kind ?? ""}>
            {k.keyword}
          </span>
        );
      })}
    </div>
  );
}

export function InsightPanel({
  documentId,
  document,
  onOpenPreview,
}: {
  documentId: string | null;
  /** Optional: pass the selected DocumentCard so the "권한·ACL" tab can render without a refetch. */
  document?: DocumentCard | null;
  onOpenPreview?: (target: PreviewTarget) => void;
}) {
  const [tab, setTab] = useState<Tab>("toc");
  const [toc, setToc] = useState<TocNode[]>([]);
  const [keywords, setKeywords] = useState<KeywordItem[]>([]);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [quality, setQuality] = useState<DocumentQuality | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!documentId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const load =
      tab === "toc"
        ? getToc(documentId).then((d) => !cancelled && setToc(d))
        : tab === "keywords"
          ? getKeywords(documentId).then((d) => !cancelled && setKeywords(d))
          : tab === "graph"
            ? getGraph(documentId).then((d) => !cancelled && setGraph(d))
            : getQuality(documentId).then((d) => !cancelled && setQuality(d));
    load
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "failed"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [documentId, tab]);

  if (!documentId) {
    return (
      <p className="pane-placeholder">
        문서를 하나 선택하면 목차·키워드·그래프가 표시됩니다 / Select one document to see insight.
      </p>
    );
  }

  return (
    <div className="insight">
      <div className="insight-tabs" role="tablist">
        {(["toc", "keywords", "graph", "quality", "access"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={`insight-tab${tab === t ? " active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "toc"
              ? "목차"
              : t === "keywords"
                ? "키워드"
                : t === "graph"
                  ? "그래프"
                  : t === "quality"
                    ? "품질"
                    : "권한·ACL"}
          </button>
        ))}
      </div>

      <div className="insight-content">
        {tab !== "access" && loading && <p className="pane-placeholder">불러오는 중… / loading…</p>}
        {tab !== "access" && error && <p className="upload-error">{error}</p>}
        {!loading && !error && tab === "toc" && (
          <TocTree
            nodes={toc}
            onJump={
              onOpenPreview && documentId
                ? (n) => onOpenPreview({ documentId, title: n.title, page_no: n.page_no })
                : undefined
            }
          />
        )}
        {!loading && !error && tab === "keywords" && <KeywordCloud keywords={keywords} />}
        {!loading && !error && tab === "graph" && <ForceGraph graph={graph} />}
        {!loading && !error && tab === "quality" && <QualityPanel quality={quality} />}
        {tab === "access" && <AccessPanel document={document ?? null} />}
      </div>
    </div>
  );
}
