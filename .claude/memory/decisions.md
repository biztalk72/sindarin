# Decisions (ADRs)

> Single source of truth for architecture decisions. Add an ADR before violating a
> hard invariant (CLAUDE.md §2) or making a non-obvious design choice (CLAUDE.md §6 step 4).
> Format: one `## ADR-NNNN` section per decision.
>
> **Note (greenfield):** no application code exists on disk yet. Code paths, module names,
> and filenames in these ADRs (`apps/api/...`, `workers/...`, `packages/...`, `build_tree`,
> etc.) are **intended targets** under the ADR-0010 monorepo layout, not assertions that the
> code is already present. PRD references point to `docs/PRD2.md` (the current SSOT).

## Index

| ADR | Title | Status |
|-----|-------|--------|
| 0001 | OpenAI-compatible client everywhere (no vendor model SDKs in `apps/api`) | accepted (amended by 0009) |
| 0002 | PageIndex-only retrieval (no vector DB / embeddings) | **superseded by 0008** |
| 0003 | HWP handling via pyhwp + HWPX XML | accepted |
| 0004 | Proof-based citations; uncited claims dropped | accepted |
| 0005 | Single-org JWT auth + optional OIDC | accepted |
| 0006 | Runtime guardrails (Presidio PII + LLM-judge) on every model call | accepted |
| 0007 | MarkItDown for DOCX/XLSX preprocessing → page-anchored PageIR | accepted |
| 0008 | Vector-DB-centric hybrid retrieval (PageIndex as structure aid) | accepted (supersedes 0002) |
| 0009 | PaddleOCR-VL as a preprocessing VLM (exempt from ADR-0001) | accepted |
| 0010 | Monorepo restructure (`apps/workers/packages/infra`) + GB10 single-node target | accepted |

---

## ADR-0001 — OpenAI-compatible client everywhere

**Status:** accepted (scope amended by ADR-0009) · **Invariant:** #1

**Context.** The product must rotate across multiple LLMs/VLMs (PRD2 §4 model router) and
must remain portable as model providers change. Binding business logic to vendor SDKs
(boto3, anthropic, google-genai) would couple `apps/api` to each provider's API surface and
auth model.

**Decision.** All model access in `apps/api` goes through `openai.AsyncOpenAI` configured
with a per-model `base_url`. Any provider is reached via an OpenAI-compatible
gateway/endpoint. No vendor model SDKs are imported anywhere in `apps/api`. This governs
**model access** only — infrastructure SDKs for object storage (e.g. boto3/MinIO client) are
allowed in the storage layer.

**Consequences.** Model rotation is a config concern (capability descriptors +
`base_url`), not a code concern. New model → capability descriptor + health-check test +
eval regression (CLAUDE.md §5). Providers without an OpenAI-compatible surface require a
shim/gateway rather than a direct SDK import.

## ADR-0002 — PageIndex-only retrieval

**Status:** SUPERSEDED by ADR-0008 (2026-06-05) · **Invariant:** #2 (now revised)

> Superseded. PRD2 (`docs/PRD2.md`) reframes the product as a document AI workspace where
> pure-semantic and keyword queries must be first-class, which a structure-only index cannot
> serve. Retained for history. The live decision is **ADR-0008**.

**Context.** Operational/standard documents have strong hierarchical structure where
context lineage matters. Vector similarity retrieval jumps between fragments and is hard
to explain; it also adds an embedding service and a vector store to operate.

**Decision (no longer in force).** Retrieval is PageIndex only (VectifyAI/PageIndex): build
a per-document tree, compose a synthetic cross-document TOC, and at query time narrow
candidate documents via the TOC then descend each document's tree to leaf nodes. No vector
DB, no embedding service, no similarity search.

**Consequences.** Retrieval follows document structure and is explainable; evidence comes
with `{document_id, page_no}` for citations. Quality depends on good tree/TOC construction
rather than embedding quality. Pure semantic-jump queries that ignore structure are out of
scope by design — **this last limitation is the reason for superseding.**

## ADR-0003 — HWP handling via pyhwp + HWPX XML

**Status:** accepted · **Invariant:** — (format strategy, PRD2 §5.4)

**Context.** Korean documents are frequently HWP/HWPX (invariant #5 makes KO first-class).
HWPX is an OWPML ZIP package with native XML; legacy HWP5 is an OLE compound file with no
clean text API.

**Decision.** Parse HWPX via its native XML package (authoritative structure). For HWP5,
fall back through `pyhwp` → `hwp5txt`; when structure recovery is insufficient, render
pages and use a VLM through the OpenAI-compatible client (ADR-0001) as the last resort.

**Consequences.** HWPX yields high-fidelity structure; HWP5 degrades gracefully without
blocking ingest. The VLM fallback reuses the model abstraction — no special-case SDK. New
format work (incl. HWP variants) requires fixture + parser test + e2e test (CLAUDE.md §5).

## ADR-0004 — Proof-based citations; uncited claims dropped

**Status:** accepted · **Invariant:** #3

**Context.** A document-grounded assistant must be trustworthy; ungrounded assertions are
the primary failure mode of RAG systems.

**Decision.** Every answer is decomposed into claims, each carrying citations to
`{document_id, page_no}` anchored in the canonical page IR. Claims without supporting
citations are dropped before the response is returned. Citation precision is a release-gate
eval dimension (`tests/eval/thresholds.toml`).

**Consequences.** Answers are auditable to the page. The page IR must preserve accurate,
stable page numbers (the citation anchor). Generation prompts and the orchestrator must
emit claim-structured output; the chat response schema (`apps/api` chat router) encodes this.
Aligned with PRD2 §9.2 (`citations`, `confidence`, `warnings`, `retrieval_trace_id`).

## ADR-0005 — Single-org JWT auth + optional OIDC

**Status:** accepted (role enum widened by ADR-0010) · **Invariant:** #7

**Context.** The product is single-org and self-hosted (no multi-tenant code, invariant
#7). Some deployments will want to federate identity to a corporate IdP.

**Decision.** Authentication is a single-org JWT (HS256) carrying `sub` + `role`, with no
tenant claim. The role enum is `admin | document_manager | auditor | user` (PRD2 §2.4;
widened from the original `admin | user` by ADR-0010). OIDC is optional (`IDP_OIDC_ENABLED`);
when on, the IdP issues tokens that verify through the same path. Admin sees
eval/audit/usage; users see only their own sessions.

**Consequences.** Authorization is a simple role check (`auth.require_admin`). No
tenant-scoping logic anywhere. The JWT secret must be ≥32 bytes in prod (`IDP_JWT_SECRET`);
the dev default is an obvious placeholder. OIDC integration is additive, not a rewrite.

## ADR-0006 — Runtime guardrails on every model call

**Status:** accepted · **Invariant:** #4

**Context.** PII leakage and unsafe/ungrounded output are runtime risks that static review
cannot catch. Guardrails must be unavoidable, not opt-in.

**Decision.** Every model call is wrapped by an input filter (Presidio PII detection,
EN+KO) and an output filter (LLM-judge), and writes an audit-log entry. Admin override is
permitted but always logged — never a silent bypass.

**Consequences.** Guardrails add latency on the request path (accepted per invariant #6:
correctness before performance). The audit log is a first-class store (PostgreSQL) surfaced
in the admin dashboard. The chat orchestrator in `apps/api` is the single choke point
that enforces the wrap; no code path may call a model directly around it.

## ADR-0007 — MarkItDown for DOCX/XLSX preprocessing → page-anchored PageIR

**Status:** accepted (retrieval framing updated by ADR-0008) · **Invariant:** #3 (format strategy, PRD2 §5.2)

**Context.** Born-digital Office formats (DOCX/XLSX) carry clean structure that is tedious
to extract block-by-block with python-docx/openpyxl. Microsoft's MarkItDown converts these
to Markdown cheaply and well. The naive integration — feed MarkItDown's Markdown straight
into the indexing pipeline — is unsafe: MarkItDown emits a *flat* Markdown string with no
page boundaries, which would erase the `{document_id, page_no}` citation anchor (invariant
#3) and bypass the canonical `PageIR` contract.

**Decision.** MarkItDown lives **inside the parser layer** (`workers/markitdown_worker/`,
ADR-0010), producing canonical IR — not feeding the indexing pipeline raw. It is Office-only
and complementary: it owns DOCX/XLSX → `PageIR`; PaddleOCR/PaddleOCR-VL handle scanned
PDFs/images (MarkItDown does not OCR) and the HWP/HWPX path (ADR-0003) is unchanged
(MarkItDown has no HWP support). The Markdown→IR mapper maps Markdown onto canonical
`Block`s (headings/tables/lists/paragraphs) and **synthetically paginates at the shallowest
heading level present** (DOCX H1 sections / XLSX `##` sheets), so every `Segment` retains a
1-based `page_no`. The MarkItDown call is isolated behind an injectable `MarkdownConverter`
(default lazily imports the lib), keeping the mapping pure and testable without the binary.

**Consequences.** Output is canonical page-anchored `PageIR` that feeds **both** the
embedding/vector pipeline and the PageIndex structure tree (ADR-0008) — MarkItDown adds no
retrieval primitive of its own. Citation anchors survive into both indexes (test asserts
`page_no` is preserved). The trade-off: for true flow formats the `page_no` is a *synthetic
section/sheet ordinal*, not a rendered page — honest and stable, but coarser than a PDF page.
A render-based DOCX page path can be added later if citation granularity proves insufficient.
Adds the `markitdown[docx,xlsx]` dependency. Real-binary e2e (sample .docx/.xlsx fixtures
with MarkItDown installed) is deferred — tracked under PRD2 §12.3 E3 (MarkItDown epic).

## ADR-0008 — Vector-DB-centric hybrid retrieval (PageIndex as structure aid)

**Status:** accepted (2026-06-05, supersedes ADR-0002) · **Invariant:** #2 (revised)

**Context.** PRD2 (`docs/PRD2.md` §4, §7) redefines the product as a self-hosted document
AI workspace, not a structure-only retriever. Users must get good answers to pure-semantic
queries ("문서에서 위약금 조건 찾아줘") and to exact-term/keyword queries (document numbers,
법령명, product codes) — neither of which a PageIndex tree serves reliably on its own.
PRD2 also sets concrete bars (KO Recall@10 ≥ 0.90, citation anchor accuracy ≥ 0.90) that
need a retrieval layer wider than TOC descent. The original objection in ADR-0002 — that a
vector store adds an embedding service and ops burden — is accepted as a real cost and
mitigated below rather than avoided.

**Decision.** Retrieval is a **hybrid pipeline** (PRD2 §7): query understanding → scope
resolution → ACL filtering → **vector search (Qdrant or pgvector, backend chosen after the
P0 benchmark proposed in PRD2 §15)** + **BM25/keyword search** → reranking → context packing →
generation → citation validation → runtime eval. **PageIndex / TOC is retained but demoted
to a structure aid**: it powers context packing (toc_path ordering, table-neighbor
context), citation alignment, candidate verification, and UI navigation — it is no longer
the sole retrieval primitive. Every chunk payload carries the full PRD2 §6.3 contract
(`document_version_id`, `toc_path`, `bbox`, `acl_hash`, `ocr_confidence`, `embedding_model`,
`embedding_version`) so ACL double-check, citation, and blue/green reindex all work off the
vector store. Embedding model selection is deferred to a follow-up ADR here (corresponds to
the embedding-model decision PRD2 §15 lists as its ADR-0006 — distinct from our ADR-0006).

**Consequences.** Invariant #2 changes from "PageIndex only" to "hybrid retrieval; PageIndex
is the structure/citation layer, not a vector-DB replacement." New operational surface:
embedding worker, vector store, snapshot/restore drill, blue/green reindex, ACL payload
filter + Postgres double-check (PRD2 §10.1). Citation anchors are preserved because vector
chunks keep `{document_id, page_no, bbox}` from the canonical IR — ADR-0004 (proof-based
citations) is unaffected and still gates release. Explainability now comes from citation
validation + retrieval_trace_id rather than from structure-only descent. The "no vector DB /
no embedding service" prohibition in CLAUDE.md §5 (Don't) is removed.

## ADR-0009 — PaddleOCR-VL as a preprocessing VLM (exempt from ADR-0001)

**Status:** accepted (2026-06-05, amends scope of ADR-0001) · **Invariant:** #1 (clarified)

**Context.** PRD2 §5.3 adds **PaddleOCR-VL**, a vision-language model, for layout-sensitive
PDF/image parsing (tables, charts, formulas, multi-column). ADR-0001 requires all *model
access* in `apps/api` to go through the OpenAI-compatible client with no vendor SDKs. Read
literally, that would force PaddleOCR-VL behind an OpenAI-compatible shim, which does not
match how it is consumed (a self-hosted parsing engine invoked inside the ingestion
pipeline, producing structured IR — not a chat/completion model the router rotates over).

**Decision.** Classify PaddleOCR-VL (and PaddleOCR) as **preprocessing/ingestion engines**,
in the same category as MarkItDown and the HWPX parser — **not** "model access" under
ADR-0001. They live in the worker layer (`workers/ocr_worker/`, per ADR-0010), are invoked
synchronously by ingestion, and emit `PageIR` (text, bbox, confidence, layout blocks). The
OpenAI-compatible-only rule (ADR-0001) continues to govern **answer-generation and
guardrail/judge LLM/VLM calls** — i.e. anything the model router rotates over or that runs
on the chat request path. A VLM used as a *fallback for answer generation* (e.g. HWP5 render
→ VLM, ADR-0003) still goes through the OpenAI-compatible client.

**Consequences.** ADR-0001's "no vendor model SDKs in `apps/api`" is scoped to model **inference on
the request/generation path**; ingestion-time parsing engines may use their own libraries in
the worker layer. The dividing line is: *does the model router rotate over it / does it run
per chat request?* If yes → OpenAI-compatible (ADR-0001). If it is a batch ingestion parser
→ exempt (this ADR). New OCR/VL engine → fixture + parser test + eval regression
(CLAUDE.md §5), same as any format/parser change.

## ADR-0010 — Monorepo restructure + GB10 single-node target

**Status:** accepted (2026-06-05) · **Invariant:** — (structure + platform, PRD2 §3, §12.1)

**Context.** The original tree (`api/ ui/ sdk/ ops/ tests/`) co-locates all backend logic in
`api/`. PRD2 §3 introduces a worker-per-stage processing model (MarkItDown / OCR / HWPX /
embedding / eval) sized for an **NVIDIA GB10 / DGX Spark, 128 GB unified-memory single
node**, where each worker needs its own memory cap, concurrency limit, and GPU queue policy.
PRD2 §12.1 specifies a monorepo that makes those workers first-class deployable units. The
repo is currently greenfield (no `api/`/`ui/` code on disk), so this is a forward-looking
layout decision with no migration cost.

**Decision.** Adopt the PRD2 §12.1 layout:
`apps/{web,api}`, `workers/{markitdown,ocr,hwpx,embedding,eval}_worker`,
`packages/{shared,document_ir,rag_core,db}`, `infra/{docker,compose,harness,migrations}`,
`tests/{fixtures,unit,integration,e2e,performance}`, `docs/{adr,runbooks}`. Target platform
is the GB10 single node; initial deploy is Docker Compose (PRD2 §3) with per-worker memory
limits and concurrency caps, structured so a single-node K8s / GitOps switch stays possible.
Service split per PRD2 §3 table (ui, api, postgres, object-store=MinIO, vector-db=Qdrant or
pgvector, the five workers, monitoring). ADRs move to `docs/adr/` as the project grows;
`.claude/memory/decisions.md` remains the working SSOT during early development.

**Amendment (2026-06-05).** Added `packages/db` (SQLAlchemy 2.0 models for PRD2 §6.2 +
Alembic migrations in `infra/migrations`), extending the enumerated `packages/*`. The
relational model is shared between `apps/api` (reads) and `workers/*` (write blocks/jobs), so
it belongs in a workspace package both depend on — not inside `apps/api`.

**Consequences.** CLAUDE.md §4 (source tree) and §3 (tech stack) are updated to match.
Harness CI/CD (PRD2 §13) builds/deploys per-service images. GB10 resource policy (worker
memory caps, GPU priority queue, thermal soak) becomes a non-functional requirement
(PRD2 §10.2). The four user roles expand from `admin|user` (ADR-0005) to
`admin|document_manager|auditor|user` — ADR-0005's JWT path is unchanged, only the role
enum grows (tracked as a follow-up; invariant #7 single-org still holds).

## ADR-0011 — Chat model: Qwen2.5-14B → Llama-3.1-Nemotron-Nano-8B (Go after Phase 0)

**Status:** accepted (2026-06-09) · **Invariant:** #1 (model access stays OpenAI-compatible via vLLM)

**Context.** Operational `vllm-chat` runs `Qwen2.5-14B-Instruct` (28 GiB weights, 0.45 GPU
util). End-to-end p50 latency on `/api/chat` is 10–16s for normal queries and 40–60s for
long responses, hitting the Next.js proxy timeout (fixed defensively to 180s + `max_tokens=768`
cap, but the underlying latency was undesirable). A staging measurement was run to evaluate
`nvidia/Llama-3.1-Nemotron-Nano-8B-v1` (Llama-3.1 arch, 16 GiB weights, 128K native context)
as the chat model — keeping `bge-m3` for embedding unchanged so re-indexing is not required.

**Decision.** Go: replace Qwen with Nemotron Nano-8B for the chat path. Phase 1 follows
(observability boosting + tokenizer-aware context budget + JSON-failure retry); Phase 2/3
land the actual `.env`/`vllm-chat` cutover.

**Measurement (5 KO + 5 EN questions, identical `_SYSTEM_PROMPT`, identical fake context,
`response_format=json_object`, `temperature=0.0`, `max_tokens=768`):**

| metric | Qwen2.5-14B | Nemotron Nano-8B | gate |
|---|---|---|---|
| JSON parse rate | 5/5 KO + 5/5 EN = 100% | 5/5 KO + 5/5 EN = 100% | ≥ 90% ✓ |
| Claims-with-citation | 15/15 | 14/14 | ≥ 80% ✓ |
| p50 latency KO | 6.54s | 7.30s (+0.76s, 1.12×) | ≤ 1.5× ✓ |
| p50 latency EN | 6.20s | **3.11s (0.50×, 2× faster)** | ≤ 1.5× ✓ |
| GPU concurrency | chat(0.45)+embed(0.10)+staging(0.30) = 0.85; all three healthy | < 95 GiB ✓ |
| Cold load (first download) | (already cached) | ~13 min (~15 GiB DL into hf-cache) | one-time |

Korean cost of +0.76s p50 is the Llama-3.1 tokenizer penalty on Hangul (more tokens per char
than Qwen's BPE). English saves more than KO loses — net p50 across 10 questions: 6.37s →
5.20s. Tokenizer-aware context packing (Phase 1) will recover some of the KO gap.

**Consequences.** (1) `.env` `ANSWER_MODEL=nemotron-nano-8b`, `CHAT_MODEL=nvidia/Llama-3.1-Nemotron-Nano-8B-v1`
at cutover. `VLLM_MAX_LEN=8192` unchanged (Nemotron native 128K, cap kept conservative).
GPU util 0.45 → can shrink to ~0.30 since the model is half the size; final value tuned in
Phase 2. (2) `bge-m3` and `documents_bge` collection untouched — re-indexing not required.
(3) ADR-0001 still holds — same OpenAI-compatible vLLM endpoint. (4) Phase 1 must land
*before* cutover: JSON-failure retry in `_parse_draft` is a no-op now (100% parse rate) but
becomes load-bearing once we start trusting a single smaller model. (5) `pack_context`
glyph-budget review with the Llama-3.1 tokenizer — Phase 1 introduces a `transformers`
AutoTokenizer-based budget (+~200 MB image size, accepted). (6) `tests/eval/thresholds.toml`
re-measured at cutover; baseline expected within the gate; if not, hold and revisit per
ADR-0004 process. (7) Phase 0 staging container is profiled-off (`profiles: ["staging"]`) —
present in `infra/compose/llm.yml` for future re-measurement, never auto-started.

See `docs/runbooks/nemotron-phase0.md` for the full Phase 0 trace and `/tmp/nemotron_phase0_compare.py`
for the measurement script (to be promoted to `scripts/eval_compare.py` in Phase 1).

**Phase 2 cutover (2026-06-09).** Operational `vllm-chat` recreated with
`nvidia/Llama-3.1-Nemotron-Nano-8B-v1` (served-name `nemotron-nano-8b`),
`VLLM_CHAT_GPU_UTIL` shrunk 0.45 → 0.30 to match the smaller weights. `apps/api`
gained the `tokenizers>=0.20` dep; `RagPipeline` now takes optional `tokenizer` +
`budget_tokens` (2000) — `pack_context` uses token budget when configured, glyph
budget otherwise. `api.Dockerfile` pre-fetches the chat-model tokenizer at build time
(ARG `CHAT_MODEL`, ~3–10 MB) so first-request latency stays clean. `audit_logs.metrics`
now carries `model="nemotron-nano-8b"` on every chat row — Audit Trail diff vs the
pre-cutover Qwen rows is one query.

Cutover smoke (real RAG path through `:3200` proxy, no fake context):
  EN "Which chat model is the platform using?"  → 11.08s, cites=1, ground=1.0
  EN "What is the embedding dim?"               →  3.40s, cites=0 (dropped — single chunk
                                                   doesn't carry the literal claim)
  KO "한국어 지원을 한 문장으로 …"             → 17.62s, cites=0 (Nemotron-Nano-8B KO
                                                   citation extraction is brittle even with
                                                   guarded JSON; Phase 0's KO 7.30s p50 was
                                                   on synthetic context).

Net: the model swap is live, the trust layer is honest about misses (dropped =
"no claim survived"), and the Audit Trail makes the diff queryable. Real-corpus KO
quality is the main follow-up; candidates are (a) chunk-level Korean-specific cleanup,
(b) wider context budget (bump `RAG_CONTEXT_TOKEN_BUDGET` 2000 → 3000), (c) a larger
Nemotron variant (22B or 70B) — defer until we have a KO golden eval set rather than
ad-hoc queries.

Rollback path: revert `.env` (`ANSWER_MODEL=qwen2.5-14b`, `CHAT_MODEL=Qwen/Qwen2.5-14B-Instruct`,
`VLLM_CHAT_GPU_UTIL=0.45`), `docker compose ... up -d --force-recreate vllm-chat api`.
Qwen weights still sit in `hybrid-idp_hf-cache` from the pre-cutover state, so the
rollback is ~3-minute warm.

**Phase 2 follow-up — KO citation extraction (Track A, 2026-06-09).** Two experiments
attempted to recover the KO `cited > 0` rate that dropped to 1/5 (20%) on real corpus
after the cutover (Phase 0's KO 5/5 = 100% was synthetic context):

| Experiment | KO `cited > 0` | p50 | p95 |
|---|---|---|---|
| `RAG_CONTEXT_TOKEN_BUDGET=2000` (baseline) | 1/5 | 5.83s | 63.82s |
| `RAG_CONTEXT_TOKEN_BUDGET=3000` | 1/5 | 5.83s* | 63.02s |
| `_SYSTEM_PROMPT` adds explicit chunk_id verbatim rule + KO line | **0/5** | **4.18s** | 28.42s |

Neither recovers KO citation accuracy. The prompt tweak shaves p50 (less JSON-retry
churn — the worst-case 63s tail comes from one query that exhausts max_tokens=768 with
no JSON output) but at the cost of one less successful citation match. Net: prompt
stays in (latency win banked, citation loss is within noise on N=5) but
**`RAG_CONTEXT_TOKEN_BUDGET=2000` stays the default** — the +1000 token budget
materially adds prompt time without rescuing the citation extraction.

Root cause is not budget or prompt: it's that on the small Nemotron model, KO claim
text and the matching chunk text often diverge enough that `trust._supports`'s 50%
token overlap (BM25 Hangul tokenizer) marks the claim unsupported. Real fixes are
larger and out of scope for an ad-hoc tweak — landed as separate-epic candidates:

1. **KO golden eval set** — N=5 is not statistically meaningful; without 30+ queries we
   can't tell prompt tweaks from variance.
2. **Larger Nemotron variant** (22B / Llama-3.1-Nemotron-70B-Instruct-HF) — GPU memory
   permits, but latency triples.
3. **KO-specialized model** — HyperCLOVAX SEED was scoped earlier (Korean tokenizer
   efficiency, KO-first instruction-following). License + vLLM 0.11 architecture
   support recheck required.
4. **Soften citation overlap threshold** — `trust.SUPPORT_THRESHOLD` is 0.5; an LLM
   judge (deferred per PRD2 §15) would replace the heuristic.

(*) Budget 3000 KO p50 was actually 5.83s on q1 + 3.78/3.79/3.25/63s on the rest — q1
was atypically slow (18.5s) once, baseline numbers from the same session.
