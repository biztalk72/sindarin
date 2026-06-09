"""Runtime settings loaded from environment (see env.example)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    app_log_level: str = "info"
    app_default_locale: str = "ko"

    # Auth (ADR-0005)
    idp_jwt_secret: str = "dev-only-insecure-placeholder-change-me"
    idp_jwt_alg: str = "HS256"
    idp_oidc_enabled: bool = False
    idp_token_ttl_minutes: int = 720
    idp_bootstrap_admin_email: str = ""  # if set, ensured on startup with admin role
    idp_bootstrap_admin_password: str = ""

    # Models (ADR-0001: OpenAI-compatible only)
    openai_api_key: str = ""
    openai_base_url: str = "http://localhost:8080/v1"
    answer_model: str = "default-answer"
    # HuggingFace model ID — used only by the tokenizer-aware context budget (ADR-0011 /
    # Phase 2). Distinct from `answer_model` (the vLLM served-model-name). Left empty
    # disables token-aware packing (falls back to glyph budget).
    chat_model: str = ""
    # Token budget for `pack_context` when a tokenizer is available. ≈ 2000 tokens covers
    # the same retrieval fan-out the 6000-char glyph budget did on Qwen, with headroom
    # for the system prompt (~200 tok) and the 768 max_tokens cap.
    rag_context_token_budget: int = 2000
    embedding_model: str = ""
    embedding_base_url: str = ""  # falls back to openai_base_url
    embedding_dim: int = 1536

    # Vector DB (ADR-0008)
    vector_db_kind: str = "qdrant"
    vector_db_url: str = "http://vector-db:6333"
    vector_collection: str = "documents"


settings = Settings()
