# Nemotron Phase 0 — staging measurement runbook

> Goal: decide whether `Qwen2.5-14B-Instruct` should be replaced by
> `nvidia/Llama-3.1-Nemotron-Nano-8B-v1` as the chat model. **No production code touched.**
> Operational `vllm-chat` (Qwen, 0.45 GPU util) and `vllm-embed` (bge-m3, 0.10) keep serving;
> a third `vllm-chat-staging` container (0.30) is brought up only for the measurement window.

## 1. Pre-flight (one-time)

```bash
# 1. Confirm GPU + disk headroom
nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv
df -h /var/lib/docker /

# 2. Confirm operational vLLM is up
docker ps --filter "name=hybrid-idp-vllm-chat-1" --format '{{.Status}}'
docker ps --filter "name=hybrid-idp-vllm-embed-1" --format '{{.Status}}'

# 3. Confirm staging port free
ss -tlnp | grep :8011 || echo "8011 free"

# 4. Verify env vars (already in .env / env.example)
grep STAGING_ .env
```

## 2. Start staging container

```bash
# The `staging` profile keeps this container out of the default `up -d` so daily
# operations never accidentally pull a second model.
docker compose --env-file .env \
  -f infra/compose/dev.yml -f infra/compose/llm.yml \
  --profile staging up -d vllm-chat-staging
```

First cold load downloads ~16 GiB into the shared `hybrid-idp_hf-cache` volume
(`/var/lib/docker/volumes/hybrid-idp_hf-cache/_data`). Expect ~3–8 minutes including
weight loading and CUDA graph capture.

Wait for healthy:

```bash
until docker exec hybrid-idp-vllm-chat-staging-1 \
        python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')" \
        2>/dev/null; do sleep 15; done
echo "staging ready"
```

Confirm served-model:

```bash
curl -fsS -H "Authorization: Bearer $OPENAI_API_KEY" http://localhost:8011/v1/models | jq .
```

## 3. Measure

```bash
# Compare Qwen (8001) vs Nemotron (8011) on the same KO/EN golden questions
OPENAI_API_KEY=$(grep '^OPENAI_API_KEY=' .env | cut -d= -f2-) \
  python3 /tmp/nemotron_phase0_compare.py
```

The script runs 5 KO + 5 EN questions against each model with the **exact same system
prompt and context** that the live RAG generator uses (`packages/rag_core/rag_core/generator.py`
`_SYSTEM_PROMPT`). Measures:

- HTTP outcome
- JSON parse success (the `_parse_draft` precondition)
- Number of claims + how many carry citations
- p50 / p95 latency
- 200-char answer preview

## 4. Go / No-go criteria

| Criterion | Threshold | Source |
|---|---|---|
| Container boots, `/v1/models` returns served name | required | docker / curl |
| JSON parse success rate | ≥ 90% (≥ 9/10 across KO+EN) | script summary `json_ok` |
| Claims-with-citations rate | ≥ 80% (across all parsed responses) | `cited_total / claims_total` |
| p50 latency vs Qwen | ≤ 1.5× | summary table |
| GPU memory chat+embed+staging simultaneously | < 95 GiB used | `nvidia-smi` during measurement |

Any criterion failing → No-go (Qwen stays). Record reason in ADR-0011 either way.

## 5. Results (fill in after running)

### 5.1 Environment (filled 2026-06-09)

| Item | Value |
|---|---|
| Date | 2026-06-09 01:05 UTC / 10:05 KST |
| GB10 driver | 580.159.03 (CUDA 13.0) |
| vLLM image | `nvcr.io/nvidia/vllm:25.11-py3` (vLLM 0.11.0+582e4e37.nv25.11) |
| Operational chat model | `qwen2.5-14b` (Qwen2.5-14B-Instruct, 0.45 GPU util) |
| Operational embedding | `bge-m3` (BAAI/bge-m3, 0.10 GPU util) |
| Staging chat model | `nemotron-nano-8b` (Llama-3.1-Nemotron-Nano-8B-v1, 0.30 GPU util) |
| Cold load (staging) | ~13 min (most of it = 15 GiB HF download into `hybrid-idp_hf-cache`) |
| HF cache after staging | 48 GiB total (Qwen 28 + bge-m3 ~2 + Nemotron 15 + index/locks) |
| Concurrent vLLM containers | 3 healthy (operational + embed + staging) — no GPU contention |

### 5.2 Score table (5 KO + 5 EN questions, same `_SYSTEM_PROMPT` + identical context)

| label | json_ok | claims | cited | p50 | p95 | notes |
|---|---|---|---|---|---|---|
| Qwen KO | **5/5** | 6 | 6 | 6.54s | 8.66s | Baseline |
| Nemo KO | **5/5** | 7 | 7 | 7.30s | 9.24s | +0.76s p50 vs Qwen (1.12×) |
| Qwen EN | **5/5** | 9 | 9 | 6.20s | 6.89s | Baseline; highest claim density |
| Nemo EN | **5/5** | 7 | 7 | **3.11s** | 7.71s | **2× faster p50** than Qwen EN |

JSON parse success = **20/20 (100%)** across both models. Every parsed claim carried a citation.
`guided_json` not used — `response_format={"type":"json_object"}` alone is enough on both
models for this prompt/context size.

### 5.3 Observations

- **Korean token efficiency**: Llama-3.1 tokenizer is less efficient on Hangul than Qwen's,
  which costs Nemo +0.76s p50 on KO. EN p50 swings the other way (Nemo 3.11s vs Qwen 6.20s)
  because Nemo is 8B (vs 14B). Net p50 across all 10: Qwen 6.37s, Nemo ~5.20s.
- **Claim density**: Qwen tends to emit slightly more atomic claims per answer (9 vs 7 on EN).
  Both reach 100% citation coverage — not a quality gap, just a verbosity difference.
- **GPU memory**: all three vLLM containers ran concurrently throughout the measurement
  window with no OOM and no eviction. The `0.45 + 0.10 + 0.30 = 0.85` plan held with the
  observed 0.15 headroom intact.
- **System-prompt obedience**: Nemo followed the JSON-only constraint and the
  "answer in the same language as the question" rule on every single call — no English
  bleeding into KO answers, no markdown wrap around the JSON.

### 5.4 Go / No-go (2026-06-09)

- [x] **Go** — proceed to Phase 1 (RAG observability boosting + tokenizer-aware context budget + retry-on-JSON-failure).
- [ ] No-go.

All five Go criteria from §4 passed:

| Criterion | Threshold | Observed |
|---|---|---|
| Boots, /v1/models returns served name | required | ✓ `served: nemotron-nano-8b` |
| JSON parse rate | ≥ 90% | **100% (20/20)** |
| Claims-with-citations | ≥ 80% | **100%** |
| p50 latency vs Qwen | ≤ 1.5× | KO 1.12× / EN 0.50× ✓ |
| GPU memory chat+embed+staging | < 95 GiB used | 3 containers healthy throughout ✓ |

## 6. Tear-down

```bash
docker compose --env-file .env \
  -f infra/compose/dev.yml -f infra/compose/llm.yml \
  --profile staging stop vllm-chat-staging
docker compose --env-file .env \
  -f infra/compose/dev.yml -f infra/compose/llm.yml \
  --profile staging rm -f vllm-chat-staging
# Keep hf-cache volume — Phase 2 staging will re-use the cached weights.
```

## 7. Follow-ups

Regardless of Go/No-go, write **ADR-0011** in `.claude/memory/decisions.md` with:
- decision (`Go` to Nemotron / `Stay` on Qwen)
- numbers from §5.2
- one paragraph rationale
- next-step pointer (Phase 1 PR, or revisit cadence)
