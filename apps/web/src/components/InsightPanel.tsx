"use client";

import { useEffect, useState } from "react";

import {
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

type Tab = "toc" | "keywords" | "graph" | "quality";

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

function KeywordGraph({ graph }: { graph: GraphData }) {
  const { nodes, edges } = graph;
  if (nodes.length === 0) return <p className="pane-placeholder">그래프 없음 / no graph</p>;
  const W = 320;
  const H = 320;
  const cx = W / 2;
  const cy = H / 2;
  const r = 130;
  const pos = new Map<string, { x: number; y: number }>();
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    pos.set(n.id, { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) });
  });
  const maxW = Math.max(1, ...edges.map((e) => e.weight));
  return (
    <svg className="kw-graph" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="keyword graph">
      {edges.map((e, i) => {
        const a = pos.get(e.source);
        const b = pos.get(e.target);
        if (!a || !b) return null;
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="#9bbcf5"
            strokeOpacity={0.25 + 0.6 * (e.weight / maxW)}
            strokeWidth={1 + 2 * (e.weight / maxW)}
          />
        );
      })}
      {nodes.map((n) => {
        const p = pos.get(n.id)!;
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={5} fill="#2563eb" />
            <text x={p.x} y={p.y - 8} textAnchor="middle" fontSize="10" fill="#1c2024">
              {n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function InsightPanel({
  documentId,
  onOpenPreview,
}: {
  documentId: string | null;
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
        {(["toc", "keywords", "graph", "quality"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={`insight-tab${tab === t ? " active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "toc" ? "목차" : t === "keywords" ? "키워드" : t === "graph" ? "그래프" : "품질"}
          </button>
        ))}
      </div>

      <div className="insight-content">
        {loading && <p className="pane-placeholder">불러오는 중… / loading…</p>}
        {error && <p className="upload-error">{error}</p>}
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
        {!loading && !error && tab === "graph" && <KeywordGraph graph={graph} />}
        {!loading && !error && tab === "quality" && <QualityPanel quality={quality} />}
      </div>
    </div>
  );
}
