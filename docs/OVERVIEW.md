# Hybrid IDP — Overview

Self-hosted document AI workspace with citation-bound chat, runtime guardrails, and
full data-governance UI. Designed to run on a single NVIDIA GB10 node with no data
egress (ADR-0001, ADR-0006, ADR-0010, PRD2 §3).

---

## 1. Features

### Document workspace
- **3-pane UI** (PRD2 §8.1): Document Library (left) / Chat + Preview (center) / Insight Panel (right).
- **Multi-format ingestion**: `.docx .xlsx .pptx .html .csv .json .xml .hwpx .pdf` via dedicated workers (markitdown, ocr, hwpx). All flow through a single `DocumentIR` schema validated by `document_ir.validate_ir`.
- **OCR** for scanned PDFs (PaddleOCR + PaddleOCR-VL, layout-aware, ADR-0009; some stages env-blocked pending GPU model deploy).
- **NUL-byte sanitisation** at ingest boundary so binary leakage from PDFs/DOCX never breaks Postgres TEXT columns.
- **Force-directed keyword graph** in the Insight Panel (drag-reactive, hand-rolled — no d3 dep).
- **Document quality** tab (extraction coverage, OCR confidence, parser warnings).
- **Citation chip click** scrolls preview to the source span.

### Retrieval & RAG
- **Hybrid retrieval** (ADR-0008): vector (Qdrant) + BM25 keyword + PageIndex structure aid. **ACL payload filter + Postgres double-check** on every search (PRD2 §10.1).
- **Citation-first answers** (ADR-0004): per-claim JSON, validated by 50% token overlap against the cited span. Unsupported claims **dropped** — answer is honest "근거를 찾을 수 없음" rather than ungrounded.
- **Confidence signals** returned per chat: `groundedness`, `citation_coverage`, `retrieval_quality`.
- **Bilingual KO/EN** first-class — Hangul-aware BM25 tokenizer, KO system-prompt line, KO citation chunk_id verbatim rule.
- **Token-aware context budget** (`pack_context`) — HuggingFace `tokenizers` consulted when the configured chat model resolves a tokenizer; glyph budget fallback when not. Recovers cross-model KO/EN token efficiency.
- **JSON-failure retry** — `_parse_draft` returns None on bad JSON, generator retries once with `temperature=0.2`, surfaces `model_outcome` (`ok` / `json_retry` / `json_failed`) in `ChatResult.warnings`.

### Guardrails (ADR-0006, runtime, not opt-in)
- **PII detection + redaction** (regex): rrn, biz_no, credit_card, email, KR phone. Both input + output paths.
- **Prompt-injection strip** from retrieved document context (EN + KO patterns).
- **Override workflow** — admin records a bypass intent (kind/policy/reason ≥8 chars/TTL 1-1440 min), full audit. Audit-only today; runtime application is the D1b follow-up.

### Data governance
- **Document classification** — `SecurityLevel` 4-tier (public/internal/confidential/restricted). Read view in workspace `권한·ACL` tab; admin overview at `/policy/documents`.
- **External-egress sentinel** — `OPENAI_BASE_URL` / `EMBEDDING_BASE_URL` checked against the in-network host list; sticky yellow banner under the topbar when `external: true`.
- **DSR (Data Subject Requests)** — user opens `export` (audit count + owned docs summary) or `forget` (anonymise `audit_logs.actor_id` + tombstone email + drop ACL grants); admin processes.

### Observability & compliance
- **Per-chat audit row** — every `/api/chat` writes ULID `event_id`, `trace_id`, `kind`, `outcome`, `metrics` JSONB (duration_ms, model, claims_supported, groundedness, retrieval_quality, guardrails counts, warnings, language).
- **Daily-overlap activity log files** (GP2) — `events-YYYY-MM-DD.jsonl` written by `apps/api/app/event_log.py`; overlap window `[D-1 23:50, D+1 01:10)` means boundary events land in two files (each with its own `log_date`). Never raises — disk-full / RO fs drops the file log; DB row stays authoritative.
- **Activity Logs page** — DB tab (filterable by `kind` / `outcome`) and File tab (date picker over the daily files).
- **Audit Trail page** — row-expand viewer that surfaces the full `metrics` JSONB.
- **Compliance Report page** — date-range aggregate cards (total events, by_kind, by_outcome, by_model histogram, chat p50/p95, guardrail hit totals) + StreamingResponse CSV download with the 17 GP1 observability columns.

### Auth & roles (ADR-0005, ADR-0010)
- Single-org JWT (HS256, 12h TTL); OIDC optional path scaffolded.
- 4 roles: `admin`, `document_manager`, `auditor`, `user`. Admin override is permitted but **always logged**.
- Bootstrap admin from env on startup (idempotent).

### UI shell (Shards-Dashboard-React inspired)
- Sidebar (220 px) + topbar (60 px) + body. 4 sidebar groups visible to admin/auditor:
  - **MAIN** — Document AI
  - **MONITORING** — Health & Metrics, Activity Logs
  - **GUARDRAILS & POLICY** — Guardrails, Documents & ACL
  - **AUDIT & COMPLIANCE** — Audit Trail, DSR Requests, Compliance Report
- Shards palette + Bootstrap 4 base + Poppins (next/font). Tabler Icons. SecurityLevel + status badges, hover-lift document cards, pill citation chips, card-shadow chat bubbles.

---

## 2. Frameworks & technologies

### Backend (`apps/api`, `packages/*`, `workers/*`)

| Layer | Tech |
|---|---|
| Language | Python 3.12 |
| Web | FastAPI ≥ 0.115, uvicorn |
| ORM + migrations | SQLAlchemy 2.0, Alembic |
| Validation | pydantic 2 + pydantic-settings |
| DB driver | psycopg 3 |
| Auth | PyJWT (HS256, ADR-0005) |
| Model access | `openai` SDK against OpenAI-compatible endpoints (ADR-0001) |
| Tokenizer | HuggingFace `tokenizers` (rust-backed, no torch) |
| RAG core (in-house) | `rag_core` — chunker, retrieval, vectorstore, BM25, generator, trust, guardrails, pipeline |
| Workers | `markitdown_worker`, `ocr_worker` (PaddleOCR + PaddleOCR-VL), `hwpx_worker`, `embedding_worker`, `eval_worker` |
| Package manager | `uv` workspace (lockfile pinned) |

### Frontend (`apps/web`)

| Layer | Tech |
|---|---|
| Framework | Next.js 15 (App Router, `output: "standalone"`) |
| UI library | React 19, TypeScript 5.5 |
| Styling | Bootstrap 4.6 + shards-ui 3.0 (CSS only — no React 16 components) |
| Icons | `@tabler/icons-react` 3.x |
| Fonts | `next/font/google` Poppins |
| i18n | `next-intl` 3.x |
| Tests | Vitest + Testing Library |
| Lint | ESLint 9 (flat config via eslint-config-next) |

### Models

| Role | Model | Notes |
|---|---|---|
| Chat | `nvidia/Llama-3.1-Nemotron-Nano-8B-v1` (served `nemotron-nano-8b`) | Llama-3.1 arch, 128K native context, 0.30 GPU util |
| Embedding | `BAAI/bge-m3` (served `bge-m3`) | dim 1024, 0.10 GPU util |
| Serving | vLLM 0.11 on `nvcr.io/nvidia/vllm:25.11-py3` (sm_100 Blackwell build) |
| Rollback | Qwen2.5-14B-Instruct weights still in `hf-cache` for ~3-min warm rollback |

### Infrastructure

| Component | Tech |
|---|---|
| Container orchestration | Docker Compose (`dev.yml` + `llm.yml` overlay + `prod.yml` for registry deploy) |
| Relational store | PostgreSQL 16 |
| Vector DB | Qdrant (ADR-0008; pgvector remains an open option) |
| Object store | MinIO (S3-compatible) |
| Inference | vLLM (OpenAI-compatible per-model `base_url`, ADR-0001) |
| Target node | NVIDIA GB10 (Grace Blackwell, aarch64, 128 GB unified memory) |
| Profiles | `staging` profile gates `vllm-chat-staging` so it never starts in default `up -d` |

### Audit / files

- `audit_logs` table = system of record.
- `events-YYYY-MM-DD.jsonl` daily files, host bind-mounted (`./logs:/srv/var/log/hybrid-idp`).
- Both surfaces share the same ULID `event_id` for cross-reference.

---

## 3. Minimum system requirements

### Hardware (production target)
- NVIDIA Grace Blackwell GB10 (sm_100 capability)
- ≥ 120 GiB unified memory (the deployed VLLM containers use 0.30 chat + 0.10 embed ≈ 50 GiB; rest is OS + KV cache headroom)
- ≥ 100 GiB disk for: HuggingFace model cache (~48 GiB Qwen+bge-m3+Nemotron), Postgres data, Qdrant data, MinIO data, daily log files
- aarch64 driver: NVIDIA 580.x+, CUDA 13.0
- 1 Gbps network (first-time HF download)

### Hardware (dev / small deploy)
- A100 40 GB or 2× A100 80 GB also works if the model `gpu_memory_utilization` caps are recomputed.
- 64+ GB RAM, 50+ GB disk minimum if Qwen rollback path isn't needed.

### Host software
- Linux 6.x
- Docker 27+ with NVIDIA Container Toolkit
- Python 3.12 (for `uv run alembic upgrade head` from host; alternatively all migrations run inside the api container)
- Node 20+ (only needed for `npm test` / local web dev)
- `uv` ≥ 0.4 if developing on host

### First-boot footprint
- ~48 GiB HF model cache (Qwen 28 + bge-m3 2 + Nemotron 15 + indexes)
- Postgres init < 100 MiB
- Qdrant empty collection < 10 MiB
- MinIO empty bucket < 1 MiB
- Web standalone build < 100 MiB image

---

## 4. Comparison to conventional RAG chat

A conventional RAG-chat stack typically pairs a vector DB with a hosted LLM API
(OpenAI / Anthropic) and a thin orchestrator (LangChain / LlamaIndex). Hybrid IDP is
designed for the opposite quadrant: **self-hosted, governance-heavy, citation-bound,
single-tenant.**

| Dimension | Conventional RAG chat | Hybrid IDP |
|---|---|---|
| **Retrieval** | Vector similarity, single-stage | Hybrid: vector (Qdrant) + BM25 + PageIndex aid + ACL payload filter + Postgres double-check |
| **Citations** | Post-hoc reference list at best | Per-claim JSON, lexical-overlap validated; unsupported claims **dropped** before reaching the user |
| **Trust signal** | "trust me" | Returns `groundedness`, `citation_coverage`, `retrieval_quality`; eval-gated release (`tests/eval/thresholds.toml`) |
| **Multi-format ingestion** | One generic loader, often lossy on Office/HWP | Dedicated workers per format (`markitdown / ocr / hwpx`) emitting a validated `DocumentIR` |
| **Guardrails** | External (Guardrails AI / NeMo Guardrails) | Built-in PII regex + injection strip + audit on every model call (ADR-0006). Override workflow with mandatory reason + TTL |
| **Audit trail** | Optional, application-level | First-class: `audit_logs` row + daily file log per chat with ULID, trace, metrics, guardrail hits |
| **Data governance** | Minimal; "send to OpenAI" path | SecurityLevel 4-tier, ACL double-check, DSR export/forget, Compliance Report (CSV today, PDF later), external-egress sentinel banner |
| **Hosting** | Cloud LLM API, optional self-hosted vector | Fully self-hosted on a single GB10 node; vLLM with sm_100 build; no data egress |
| **Model swap** | Hand-edit config, hope tokenization holds | ADR-driven cutover; token-aware context budget rebinds to the new tokenizer; pre/post diff is one SQL query (`audit_logs.metrics.model`) |
| **Korean support** | English-tokenizer assumptions | Hangul-aware BM25, KO system-prompt line, bilingual UI strings (`/`-separated) |
| **Multi-tenancy** | Often org-keyed | Single-org by design (invariant #7); admin/auditor/document_manager/user roles |
| **Streaming** | Usually streamed | Non-streamed today; SSE is a flagged follow-up |
| **Recovery** | Rebuild from scratch | Qwen weights retained in `hf-cache` → ~3-minute warm rollback after a model swap |
| **Observability storage** | Often ad-hoc, sometimes only logs | Two-surface: DB (Audit Trail, queryable) + JSON-Lines daily files (overlap-window forensic dumps) |
| **Bug surface** | Hidden vendor decisions | Every silent-failure path surfaces a `ChatResult.warnings` line ("model returned non-JSON; recovered on retry", "no claim survived citation validation", etc.) |
| **Failure ethic** | "Fluent answer wins" | **"Proof beats fluency"** — answer says "근거를 찾을 수 없음" if nothing survives validation (PRD2 §7.1) |

### Where conventional RAG wins
- **First-deploy time**: 30 minutes vs Hybrid IDP's first model-download window of ~15 minutes + per-format worker tuning.
- **Latency**: Hosted GPT-class models are 2–5× faster on cold paths than a single GB10 running Nano-8B (especially for KO).
- **Long context**: 128K hosted context is one click; here it's whatever the chat-served vLLM model exposes (currently `max_model_len=8192` cap by config).

### Where Hybrid IDP wins
- **Data egress**: zero, by construction.
- **Auditability**: every model call is a queryable row + a daily JSON line.
- **Governance compliance**: SecurityLevel + DSR + Compliance Report + Override audit out of the box.
- **Trust**: dropped unsupported claims is a feature, not a regression.
- **Cost determinism**: capex on one box vs per-token billing.

---

## 5. Where things sit

| Concern | Path |
|---|---|
| Always-loaded engineering guidance | `CLAUDE.md` (root) |
| Architecture decisions (ADR-0001…0011) | `.claude/memory/decisions.md` + mirror at `docs/adr/` |
| Operating runbooks | `docs/runbooks/` (`go-live.md`, `nemotron-phase0.md`) |
| Eval gate thresholds | `tests/eval/thresholds.toml` |
| Schema (auto-applied on api boot) | `infra/migrations/versions/*.py` |
| Compose | `infra/compose/{dev,prod,test,llm}.yml` |
| Live activity log files | `./logs/events-YYYY-MM-DD.jsonl` (host bind mount) |
