# Architecture Decision Records

During early development the **working SSOT for ADRs is
[`.claude/memory/decisions.md`](../../.claude/memory/decisions.md)** (ADRs 0001–0010).
Per ADR-0010, ADRs mirror into this directory as one file per decision as the project grows.

Accepted decisions:

| ADR | Title |
|-----|-------|
| 0001 | OpenAI-compatible client for model access (amended by 0009) |
| 0002 | PageIndex-only retrieval — **superseded by 0008** |
| 0003 | HWP handling via pyhwp + HWPX XML |
| 0004 | Proof-based citations; uncited claims dropped |
| 0005 | Single-org JWT auth + optional OIDC (roles widened by 0010) |
| 0006 | Runtime guardrails on every model call |
| 0007 | MarkItDown for DOCX/XLSX → page-anchored IR |
| 0008 | Vector-DB-centric hybrid retrieval (PageIndex as structure aid) |
| 0009 | PaddleOCR-VL as a preprocessing VLM (exempt from 0001) |
| 0010 | Monorepo restructure + GB10 single-node target |

Open follow-ups (not yet decided): vector-DB backend (Qdrant vs pgvector, P0 benchmark),
embedding model, model-routing strategy, UI graph library.
