# Hybrid IDP

> Single-org, **self-hosted** Intelligent Document Processing + chat workspace with
> citation-bound RAG, runtime guardrails, and end-to-end data governance.
> Target platform: NVIDIA GB10 single node. No data leaves the box.

> 🇰🇷 **한국어:** [`README.ko.md`](README.ko.md)

- **PRD / SSOT:** [`docs/PRD2.md`](docs/PRD2.md)
- **Overview & architecture summary:** [`docs/OVERVIEW.md`](docs/OVERVIEW.md)
- **Architecture decisions:** [`.claude/memory/decisions.md`](.claude/memory/decisions.md) (ADRs 0001–0011)
- **Runbooks:** [`docs/runbooks/`](docs/runbooks/) — go-live, Nemotron Phase 0
- **Project guidance:** [`CLAUDE.md`](CLAUDE.md)

---

## Highlights

- **3-pane workspace** — document library, citation-bound chat with preview, force-directed insight panel
- **Multi-format ingestion** — docx · xlsx · pptx · html · csv · json · xml · hwpx · pdf, each through a dedicated worker producing a validated `DocumentIR`
- **Hybrid retrieval** — vector (Qdrant) + BM25 + PageIndex structure aid, ACL payload filter + Postgres double-check on every search
- **Proof beats fluency** — per-claim JSON, lexical-overlap validated, unsupported claims **dropped** (returns "근거를 찾을 수 없음" rather than fabricating)
- **Runtime guardrails** — PII (rrn/biz_no/credit_card/email/KR phone) + prompt injection detect/strip on every model call (ADR-0006)
- **Bilingual KO/EN** first-class — UI, prompts, BM25 tokenizer
- **Data governance UI** — SecurityLevel 4-tier classification, DSR (export/forget), guardrail override workflow with mandatory reason + TTL, Compliance Report (summary + CSV), external-egress sentinel banner
- **Per-chat observability** — ULID `event_id` + `trace_id` + JSONB metrics on every call; daily-overlap JSON-Lines files alongside the DB row
- **Self-hosted LLM** — vLLM 0.11 on `nvcr.io/nvidia/vllm` (sm_100 Blackwell build), `Llama-3.1-Nemotron-Nano-8B-v1` chat + `bge-m3` embedding
- **Token-aware context budget** — HuggingFace `tokenizers` cached at api build time; glyph budget fallback
- **Eval-gated releases** — citation_precision ≥ 0.90, recall_at_10 ≥ 0.90, etc. block release if floors are crossed

## Tech stack

| Layer | Tech |
|---|---|
| API | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · pydantic 2 · psycopg 3 · PyJWT · openai SDK · `tokenizers` (HF) |
| RAG core (in-house) | `rag_core` — chunker, retrieval, BM25, vectorstore, generator, trust, guardrails, pipeline |
| Workers | markitdown · ocr (PaddleOCR + PaddleOCR-VL) · hwpx · embedding · eval |
| Web | Next.js 15 (App Router, standalone) · React 19 · TypeScript 5.5 · Bootstrap 4.6 + shards-ui 3.0 CSS · `@tabler/icons-react` · next-intl · vitest |
| Models | Nemotron Nano-8B (chat) · BAAI/bge-m3 (embed) · served by vLLM 0.11 (nvcr.io/nvidia/vllm:25.11-py3) |
| Infra | PostgreSQL 16 · Qdrant · MinIO · Docker Compose |
| Workspace | uv (Python) · npm (web) |

## Layout

```
apps/        web (Next.js 15) · api (FastAPI)
workers/     markitdown · ocr · hwpx · embedding · eval
packages/    shared · document_ir · rag_core · db
infra/       docker · compose · harness · migrations
tests/       unit · integration · e2e · performance · eval
docs/        adr · architecture · runbooks · OVERVIEW
```

## Quick start

```bash
make install          # uv sync (Python workspace) + web deps
make up               # docker compose up -d (api, web, postgres, qdrant, minio, workers)
# Live mode (self-hosted vLLM on the GB10):
docker compose --env-file .env -f infra/compose/dev.yml -f infra/compose/llm.yml up -d
make migrate          # alembic upgrade head
make test             # pytest + web tests
make lint typecheck   # ruff + tsc
```

See [`docs/runbooks/go-live.md`](docs/runbooks/go-live.md) for the dev → live LLM
switch (recommended path: Option B, self-hosted vLLM on the GB10 — no data egress).

## Minimum system requirements

| Item | Requirement |
|---|---|
| GPU | NVIDIA GB10 (Grace Blackwell, sm_100, 128 GB unified memory). Also runs on A100 40/80 GB with re-tuned `gpu_memory_utilization` caps. |
| Memory | ≥ 64 GiB RAM (host) |
| Disk | ≥ 100 GiB (HF model cache ≈ 48 GiB + Postgres + Qdrant + MinIO + log files) |
| Driver | NVIDIA 580.x+ · CUDA 13.0 |
| OS | Linux 6.x · Docker 27+ with NVIDIA Container Toolkit |
| Host tooling | Python 3.12 · `uv` ≥ 0.4 · Node 20+ (web dev only) |
| Network | 1 Gbps (first-time HuggingFace model download only — offline thereafter) |

## How it differs from conventional RAG chat

| Dimension | Conventional RAG chat | Hybrid IDP |
|---|---|---|
| Retrieval | Vector similarity, single-stage | Hybrid: vector + BM25 + PageIndex + ACL payload filter + Postgres double-check |
| Citations | Post-hoc reference list | Per-claim JSON, lexical-overlap validated; unsupported claims **dropped** |
| Guardrails | External (Guardrails AI / NeMo) | Runtime PII regex + injection strip on every call, with override workflow |
| Audit | Optional, application-level | First-class: `audit_logs` row + daily JSON-Lines file per chat (shared ULID) |
| Data governance | Minimal | SecurityLevel 4-tier · ACL · DSR (export/forget) · Compliance Report · egress sentinel |
| Hosting | Cloud LLM API | Fully self-hosted on a single GB10 node; vLLM with sm_100 build |
| Model swap | Hand-edit config | ADR-driven cutover with token-aware budget · pre/post diff via `audit_logs.metrics.model` |
| Korean support | Tokenizer-naive | Hangul-aware BM25 · KO system-prompt line · bilingual UI strings |
| Failure ethic | Fluent answer wins | **Proof beats fluency** — honest "근거를 찾을 수 없음" when nothing survives validation |

See [`docs/OVERVIEW.md`](docs/OVERVIEW.md) §4 for the full 14-axis comparison plus
"where each side wins."

## License

Internal — see your organisation's policy.
