// Typed client for the Hybrid IDP API. Calls are same-origin and proxied to the API by
// Next.js rewrites (see next.config.mjs), so no CORS handling is needed.

export type ChatMode = "answer" | "summary" | "compare" | "table_qa" | "risk_review";

export interface Citation {
  document_id: string;
  chunk_id: string;
  page_no: number | null;
  section_path: string[];
  source_span: string;
}

export interface Confidence {
  groundedness?: number;
  citation_coverage?: number;
  retrieval_quality?: number;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  confidence: Confidence;
  warnings: string[];
  retrieval_trace_id: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// --- auth (ADR-0005): bearer token stored client-side, sent on every API call ---

const TOKEN_KEY = "hidp_token";

export function getToken(): string | null {
  if (typeof window === "undefined" || !window.localStorage) return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : { ...extra };
}

export async function login(email: string, password: string): Promise<{ role: string; sub: string }> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  const data = (await res.json()) as { access_token: string; role: string; sub: string };
  setToken(data.access_token);
  return { role: data.role, sub: data.sub };
}

export function logout(): void {
  setToken(null);
}

export async function getMe(): Promise<{ sub: string; role: string }> {
  const res = await fetch("/api/auth/me", { headers: authHeaders() });
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  return (await res.json()) as { sub: string; role: string };
}

export interface DocumentCard {
  id: string;
  name: string;
  type: string;
  status: string;
  security_level: string;
  created_at: string | null;
  chunk_count: number;
}

async function readError(res: Response): Promise<string> {
  let detail = `request failed (${res.status})`;
  try {
    const body = await res.json();
    if (body?.detail) detail = typeof body.detail === "string" ? body.detail : detail;
  } catch {
    /* non-JSON error body */
  }
  return detail;
}

export async function postChat(
  message: string,
  mode: ChatMode = "answer",
  scopeDocumentIds: string[] = [],
): Promise<ChatResponse> {
  const body: Record<string, unknown> = { message, mode };
  if (scopeDocumentIds.length) body.scope = { document_ids: scopeDocumentIds };
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: authHeaders({ "content-type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  return (await res.json()) as ChatResponse;
}

export async function listDocuments(): Promise<DocumentCard[]> {
  const res = await fetch("/api/documents", { headers: authHeaders() });
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  return (await res.json()) as DocumentCard[];
}

export async function uploadDocument(file: File): Promise<{ document_id: string; chunks: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: form, headers: authHeaders() });
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  return (await res.json()) as { document_id: string; chunks: number };
}

// --- Insight (E10) ---

export interface TocNode {
  title: string;
  page_no: number | null;
  children: TocNode[];
}

export interface KeywordItem {
  keyword: string;
  weight: number | null;
  kind: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
}
export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  return (await res.json()) as T;
}

export async function getToc(documentId: string): Promise<TocNode[]> {
  const data = await getJson<{ toc_tree: TocNode[] }>(`/api/documents/${documentId}/toc`);
  return data.toc_tree;
}

export async function getKeywords(documentId: string): Promise<KeywordItem[]> {
  const data = await getJson<{ keywords: KeywordItem[] }>(`/api/documents/${documentId}/keywords`);
  return data.keywords;
}

export function getGraph(documentId: string): Promise<GraphData> {
  return getJson<GraphData>(`/api/documents/${documentId}/graph`);
}

export interface PreviewBlock {
  block_ref: string;
  page_no: number | null;
  block_type: string;
  text: string;
  section_path: string[];
}

export interface DocumentPreview {
  document_id: string;
  name: string;
  type: string;
  blocks: PreviewBlock[];
}

export function getPreview(documentId: string): Promise<DocumentPreview> {
  return getJson<DocumentPreview>(`/api/documents/${documentId}/preview`);
}

export interface DocumentQuality {
  document_id: string;
  name: string;
  type: string;
  security_level: string;
  status: string;
  metrics: {
    parser?: string;
    extraction_coverage?: number | null;
    ocr_confidence?: number | null;
    warnings?: string[];
    blocks?: number;
    chunks?: number;
  };
}

export function getQuality(documentId: string): Promise<DocumentQuality> {
  return getJson<DocumentQuality>(`/api/documents/${documentId}/quality`);
}

// --- Admin observability (E11, admin-only) ---

export interface AdminHealth {
  status: string;
  components: Record<string, string>;
}
export interface AdminMetrics {
  documents: number;
  chunks: number;
  users: number;
  audit_events: number;
  ingestion_jobs: Record<string, number>;
  host: { cpu_count: number | null };
  gb10_telemetry: string;
}
export interface AdminJob {
  id: string;
  document_id: string;
  document_name: string | null;
  stage: string;
  status: string;
  metrics: Record<string, unknown>;
  created_at: string | null;
}
export interface AuditEntry {
  action: string;
  actor_id: string | null;
  payload_hash: string | null;
  created_at: string | null;
  // GP1 observability fields. Null for rows created before the GP1 migration —
  // legacy AdminDashboard fixtures (without these) still validate fine because all are optional.
  event_id?: string | null;
  trace_id?: string | null;
  kind?: string | null;
  outcome?: string | null;
  metrics?: Record<string, unknown>;
}

export interface AuditFilter {
  limit?: number;
  kind?: string;
  outcome?: string;
}

export const getAdminHealth = () => getJson<AdminHealth>("/api/admin/health");
export const getAdminMetrics = () => getJson<AdminMetrics>("/api/admin/metrics");
export const getAdminJobs = () => getJson<AdminJob[]>("/api/admin/jobs");
export const getAdminAudit = (filter: AuditFilter = {}) => {
  const params = new URLSearchParams();
  if (filter.limit != null) params.set("limit", String(filter.limit));
  if (filter.kind) params.set("kind", filter.kind);
  if (filter.outcome) params.set("outcome", filter.outcome);
  const qs = params.toString();
  return getJson<AuditEntry[]>(`/api/admin/audit${qs ? `?${qs}` : ""}`);
};

// GP2 — daily-overlap activity logs (file-backed, distinct from the DB-backed audit_logs).
export interface LogEvent {
  ts?: string;
  ts_local?: string;
  log_date?: string;
  event_id?: string;
  trace_id?: string;
  kind?: string;
  outcome?: string;
  actor?: { user_id: string | null; role?: string };
  metrics?: Record<string, unknown>;
  payload_hash?: string;
}

export const getLogDates = () => getJson<string[]>("/api/admin/logs/files");
export const getLogByDate = (date: string, limit = 500) =>
  getJson<LogEvent[]>(`/api/admin/logs/by-date?date=${date}&limit=${limit}`);

// GP3 — guardrails read-only inventory + recent activity
export interface GuardrailPolicies {
  pii: Array<{ name: string; pattern: string }>;
  injection: Array<{ pattern: string }>;
}
export interface GuardrailEvent {
  event_id: string | null;
  trace_id: string | null;
  actor_id: string | null;
  created_at: string | null;
  input_pii: number;
  injection_removed: number;
  output_pii: number;
}
export const getGuardrailPolicies = () =>
  getJson<GuardrailPolicies>("/api/admin/guardrails/policies");
export const getGuardrailEvents = (limit = 50) =>
  getJson<GuardrailEvent[]>(`/api/admin/guardrails/events?limit=${limit}`);

// GP3 — external-egress sentinel
export interface EgressStatus {
  external: boolean;
  chat: { url: string; in_network: boolean };
  embed: { url: string; in_network: boolean };
}
export const getEgressStatus = () => getJson<EgressStatus>("/api/admin/compliance/egress");

// GP4 — guardrail overrides (D1: audit-only — runtime apply lands in D1b)
export interface GuardrailOverride {
  id: string;
  kind: "pii" | "injection";
  policy_name: string;
  reason: string;
  created_by: string;
  created_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  revoked_by: string | null;
  active: boolean;
}
export const getOverrides = (activeOnly = false) =>
  getJson<GuardrailOverride[]>(`/api/admin/guardrails/overrides?active_only=${activeOnly}`);
export async function createOverride(body: {
  kind: "pii" | "injection";
  policy_name: string;
  reason: string;
  ttl_minutes?: number | null;
}): Promise<GuardrailOverride> {
  const res = await fetch("/api/admin/guardrails/overrides", {
    method: "POST",
    headers: { ...authHeaders({ "content-type": "application/json" }) },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `request failed (${res.status})`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}
// GP4 D2 — Data-subject requests
export interface DsrRow {
  id: string;
  kind: "export" | "forget";
  status: "pending" | "processing" | "completed" | "rejected";
  requester_id: string;
  scope: Record<string, unknown> | null;
  created_at: string | null;
  processed_at: string | null;
  processed_by: string | null;
  result: Record<string, unknown> | null;
}

export const getMyDsr = () => getJson<DsrRow[]>("/api/dsr/me");

export async function createDsr(kind: "export" | "forget"): Promise<DsrRow> {
  const res = await fetch("/api/dsr", {
    method: "POST",
    headers: { ...authHeaders({ "content-type": "application/json" }) },
    body: JSON.stringify({ kind }),
  });
  if (!res.ok) throw new ApiError(res.status, `request failed (${res.status})`);
  return res.json();
}

export const getAdminDsr = (status?: string) =>
  getJson<DsrRow[]>(`/api/admin/dsr${status ? `?status=${status}` : ""}`);

export async function processDsr(id: string): Promise<DsrRow> {
  const res = await fetch(`/api/admin/dsr/${id}/process`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) {
    let detail = `request failed (${res.status})`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export async function revokeOverride(id: string): Promise<GuardrailOverride> {
  const res = await fetch(`/api/admin/guardrails/overrides/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(res.status, `request failed (${res.status})`);
  return res.json();
}

// Where a citation/TOC click wants to land in the preview.
export interface PreviewTarget {
  documentId: string;
  span?: string; // citation source_span — highlight blocks contained in it
  page_no?: number | null;
  title?: string; // TOC section title
}
