# Go live with a real LLM

Switches the stack from **dev mode** (deterministic embedder + extractive generator — real
but unsynthesized answers) to a real **OpenAI-compatible** endpoint (synthesized answers).

Switching the embedder changes the vector space, so all documents must be **re-embedded** into
a fresh collection (`make reindex`).

## 1. Configure the endpoint (`.env`)
```
OPENAI_API_KEY=<key>
OPENAI_BASE_URL=<https://.../v1>     # any OpenAI-compatible gateway (ADR-0001)
ANSWER_MODEL=<chat/completions model id>
EMBEDDING_MODEL=<embeddings model id>   # non-empty → enables live mode
EMBEDDING_BASE_URL=                      # blank = use OPENAI_BASE_URL
EMBEDDING_DIM=<vector size of the embedding model, e.g. 1536>
VECTOR_COLLECTION=documents_live         # NEW name — avoids the dev dim-64 'documents'
```
`openai_configured()` flips to true once `OPENAI_API_KEY` **and** `EMBEDDING_MODEL` are set;
`select_embedder`/`select_generator` then return the OpenAI implementations.

### Option B — self-hosted on the GB10 (no data leaves the node)
Start the bundled vLLM stack (chat + embeddings) on the app network:
```
docker compose --env-file .env -f infra/compose/dev.yml -f infra/compose/llm.yml up -d vllm-chat vllm-embed
```
Then in `.env` use the in-network endpoints (models/ports come from `infra/compose/llm.yml`):
```
OPENAI_BASE_URL=http://vllm-chat:8000/v1
EMBEDDING_BASE_URL=http://vllm-embed:8000/v1
ANSWER_MODEL=qwen2.5-14b
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIM=1024
VECTOR_COLLECTION=documents_bge
```
First start downloads the models (minutes); the vLLM healthchecks have a 10-min `start_period`.

## 2. Re-embed the corpus into the new collection
```
make reindex          # reads .env, embeds all document_chunks → VECTOR_COLLECTION at EMBEDDING_DIM
```

## 3. Restart the services
```
docker compose --env-file .env -f infra/compose/dev.yml up -d --build api web
```
The api re-reads `.env` (embedder/generator switch) and serves queries from
`VECTOR_COLLECTION`. New uploads embed with the real model into the same collection.

## 4. Verify
```
infra/scripts/smoke.sh http://localhost:8000     # health → login → chat
# then ask a real question via the UI; the answer is now LLM-synthesized + cited.
```

## Rollback
Set `VECTOR_COLLECTION` back to the previous collection and unset `EMBEDDING_MODEL`
(reverts to dev mode), or `make reindex` into a prior collection name and restart. The old
collection is untouched by reindex (blue/green by collection name).

## Notes
- **Embedding model + vector backend are open ADRs (PRD2 §15).** Record the chosen
  embedding model + dim and Qdrant-vs-pgvector decision in `.claude/memory/decisions.md`.
- Cost/latency now depend on the external endpoint; the eval gate (`make eval`) and guardrails
  still apply on the live path.
- Streaming (SSE) is not yet wired — answers return as a single response.
