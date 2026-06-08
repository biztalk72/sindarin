# Hybrid IDP

Single-org, self-hosted **Intelligent Document Processing** + document AI workspace with
chat-based RAG. Hybrid retrieval (vector DB + BM25 + PageIndex structure aid), multi-LLM/VLM
rotation via an OpenAI-compatible client, proof-based citations, runtime guardrails,
bilingual EN/KO. Target platform: NVIDIA GB10 single node.

- **PRD / SSOT:** [`docs/PRD2.md`](docs/PRD2.md)
- **Architecture decisions:** [`.claude/memory/decisions.md`](.claude/memory/decisions.md) (ADRs 0001–0010)
- **Project guidance:** [`CLAUDE.md`](CLAUDE.md)

## Layout

```
apps/        web (Next.js 15) · api (FastAPI)
workers/     markitdown · ocr · hwpx · embedding · eval
packages/    shared · document_ir · rag_core
infra/       docker · compose · harness · migrations
tests/       fixtures · unit · integration · e2e · performance · eval
docs/        adr · architecture · runbooks
```

## Quick start

```bash
make install          # uv sync (Python workspace) + web deps
make up               # docker compose up (dev profile)
make test             # pytest + web tests
make lint typecheck   # ruff + tsc
```

See [`infra/compose/dev.yml`](infra/compose/dev.yml) for the service topology
(ui, api, postgres, object-store, vector-db, workers, monitoring).
