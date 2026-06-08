# Hybrid IDP — CLAUDE.md

> Always-loaded project guidance. PRD: `docs/PRD2.md`. Harness ops: `docs/harness.md`.

## 1. Product

Single-org, self-hosted **Intelligent Document Processing** + document AI workspace with chat-based RAG. Hybrid retrieval (vector DB + BM25 + PageIndex structure aid, ADR-0008), multi-LLM/VLM rotation via OpenAI-compatible client, proof-based citations, runtime guardrails, bilingual EN/KO. Target platform: NVIDIA GB10 single node (ADR-0010).

## 2. Hard invariants (violate only with an ADR in `.claude/memory/decisions.md`)

1. **OpenAI-compatible for model access** — `openai.AsyncOpenAI` with per-model `base_url` for everything the model router rotates over / runs on the chat path. No vendor model SDKs in `api/`. Ingestion-time parsing engines (PaddleOCR-VL, MarkItDown, HWPX) are exempt — they're preprocessing, not model access (ADR-0001 + ADR-0009).
2. **Hybrid retrieval** — vector DB (Qdrant/pgvector) + BM25/keyword + PageIndex as the structure/citation/UI-navigation aid (ADR-0008, supersedes the old PageIndex-only rule). ACL payload filter + Postgres double-check on every search.
3. **Every answer is proof-based** — per-claim citations to `{document_id, page_no}`. Uncited claims are dropped.
4. **Guardrails are runtime** — input + output filters + audit log on every model call.
5. **Bilingual first-class** — EN/KO equal in UI, prompts, eval rubrics, parsers.
6. **Correctness before performance** — eval-gated releases; "fast and wrong" blocks release.
7. **Single-org, admin-aware** — no multi-tenant code. Admin sees eval/audit/usage; user sees own sessions.

## 3. Tech stack (change via ADR)

- **API**: Python 3.12 + FastAPI — **Frontend**: Next.js 15 (App Router) + TypeScript + next-intl
- **DB**: PostgreSQL 16 — **Blobs**: MinIO / S3-compat (`BlobStore`; LocalFS dev)
- **Models**: `openai` SDK per-model `base_url` — **Retrieval**: vector DB (Qdrant/pgvector) + BM25 + PageIndex structure aid (ADR-0008)
- **OCR**: PaddleOCR + PaddleOCR-VL (EN+KO, ADR-0009) — **HWP**: pyhwp + HWPX native XML (ADR-0003)
- **Guardrails**: Presidio PII + LLM-judge — **Eval**: LLM-judge rubrics + user feedback
- **Auth**: Single-org JWT + OIDC optional (ADR-0005); roles `admin|document_manager|auditor|user` — **Tracing/Monitoring**: OpenTelemetry → Postgres; Prometheus/Grafana
- **Platform**: NVIDIA GB10 / DGX Spark 128GB single node; Docker Compose deploy (ADR-0010)

## 4. Source tree

Scaffolded monorepo (ADR-0010 / PRD2 §12.1). Components carry stub implementations + tests; epics fill them in.

```
sindarin/
├── CLAUDE.md  pyproject.toml  pytest.ini  Makefile  env.example
├── .claude/memory/            # decisions.md (ADRs), patterns.md, session-log.md
├── apps/
│   ├── web/                   # Next.js 15: 3-pane workspace + admin (PRD2 §8)
│   └── api/                   # FastAPI: auth, ACL, upload, chat orchestration, admin (app/)
├── workers/                   # markitdown · ocr · hwpx · embedding · eval (each a uv pkg)
├── packages/
│   ├── document_ir/           # canonical IR schema + validate_ir (PRD2 §6.1) — contract parsers emit
│   ├── rag_core/              # retrieval, rerank, citation, ChunkPayload (PRD2 §6.3)
│   ├── db/                    # SQLAlchemy 2.0 models for PRD2 §6.2 (shared by api + workers)
│   └── shared/                # roles, security levels, ingestion stages
├── infra/                     # docker/ · compose/{dev,test}.yml · harness/pipeline.yml · migrations/ (alembic)
├── tests/                     # unit · integration · e2e · performance · eval/thresholds.toml · fixtures
└── docs/
    ├── PRD2.md                # PRD — current SSOT      ├── adr/         # mirror of decisions.md
    ├── architecture/overview.md  # module map          └── runbooks/    # deploy/backup/release-gate
```

Python is a uv workspace (`apps/api`, `workers/*`, `packages/*`); `apps/web` is a separate npm package.

## 5. Conventions

### Commits
Conventional commits: `feat(web|api|markitdown|ocr|hwpx|embedding|eval|rag|chat|guardrails|admin|auth|infra)`, `fix(…)`, `docs(adr)`, `chore`. API contract changes must update the UI client in the same PR.

### Testing
- New format → fixture + parser test + e2e test
- New model → capability descriptor + health-check test + eval regression
- `tests/eval/` must pass thresholds before release

### Don't
- Import vendor **model** SDKs in `apps/api` — use the OpenAI-compat client (parsing engines in `workers/` are exempt, ADR-0009)
- Run retrieval without the ACL payload filter + Postgres double-check (PRD2 §10.1)
- Ship uncited chat responses
- Bypass guardrails (admin override is logged)
- Optimize latency before eval dashboard is green

## 6. Task procedure

`Plans.md` (work ledger, `cc:TODO`/`cc:WIP`/`cc:完了`) is not yet created — generate it from PRD2 §12.3 epics when planning starts.

1. Pick a task from `Plans.md` (or PRD2 §12.3 epics until it exists).
2. Check `.claude/memory/decisions.md` and `patterns.md` for prior solutions.
3. Mark `cc:WIP`.
4. Implement + test. Update API contract / UI client if API changed. Add ADR if non-obvious.
5. Mark `cc:完了`.

## 7. References

- `docs/PRD2.md` — current PRD/SSOT: intent, success metrics (§10), epics (§12.3), release sequence (§14)
- `docs/architecture/overview.md` — module map (code → ADR) + processing flow
- `docs/harness.md` — harness framework, operating loop, memory rules
- `.claude/memory/decisions.md` — ADRs 0001–0010 (0002 superseded by 0008)
- `.claude/memory/patterns.md` — reusable solution patterns
