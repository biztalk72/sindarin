# Architecture Overview

Authoritative detail lives in [`docs/PRD2.md`](../PRD2.md) (§4 end-to-end architecture, §6
data model, §7 RAG/trust pipeline). This page is the map; PRD2 is the spec.

## Processing flow (PRD2 §4)

```
upload → format detection → preprocessing route → normalized Document IR → enrichment →
chunking → embedding → vector indexing → retrieval → reranking → answer generation →
citation validation → UI source navigation
```

PageIndex / TOC is an auxiliary structure index (citation alignment, candidate verification,
UI navigation), not a vector-DB replacement — ADR-0008.

## Module map

| Layer | Code | ADR |
|-------|------|-----|
| UI | `apps/web` | 0010 |
| API (auth, ACL, upload, chat orchestration, admin) | `apps/api` | 0001, 0005, 0006 |
| Office preprocessing | `workers/markitdown_worker` | 0007 |
| PDF/image OCR + layout VL | `workers/ocr_worker` | 0009 |
| HWPX native parse | `workers/hwpx_worker` | 0003 |
| Chunk + embed + index | `workers/embedding_worker` | 0008 |
| Citation + groundedness eval | `workers/eval_worker` | 0004 |
| Canonical IR schema | `packages/document_ir` | 0004, 0007 |
| Retrieval / rerank / citation / payload | `packages/rag_core` | 0008 |
| Relational metadata store (SQLAlchemy + Alembic) | `packages/db`, `infra/migrations` | 0010 |
| Shared types, roles, enums | `packages/shared` | 0005, 0010 |

## Platform

NVIDIA GB10 / DGX Spark, 128 GB unified memory, single node. Docker Compose deploy with
per-worker memory caps and concurrency limits (PRD2 §3, ADR-0010). Storage: Postgres
(metadata/ACL/audit/eval), MinIO/S3 (blobs), Qdrant or pgvector (vectors).
