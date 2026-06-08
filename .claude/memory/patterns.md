# Patterns

> Reusable solutions and conventions discovered during implementation. Check here
> before solving a problem that feels like it's been solved before (CLAUDE.md §6.2).
> Add a pattern when a non-obvious approach proves out and is likely to recur.

## Conventions already fixed (CLAUDE.md)

- **Model calls**: always `openai.AsyncOpenAI` with a per-model `base_url`. Never import a vendor SDK in `api/`. Bedrock Gemma4 sits behind this abstraction.
- **Retrieval**: PageIndex tree traversal only — per-doc tree + synthetic cross-doc TOC. No similarity search.
- **Citations**: every claim carries `{document_id, page_no}`; the chat layer drops uncited claims before returning.
- **Guardrails**: input (Presidio PII) + output (LLM-judge) filters + audit log wrap every model call. Admin override is logged, never silent.
- **Bilingual**: EN/KO are equal in UI, prompts, eval rubrics, and parsers — add both whenever you add one.
- **Testing gates**: new format → fixture + parser test + e2e; new model → capability descriptor + health-check + eval regression; `tests/eval/` must pass thresholds before release.

---

_(Implementation patterns go below as they are discovered.)_
