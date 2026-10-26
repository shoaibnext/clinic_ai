from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Clinic AI Receptionist API"
    app_env: str = "development"
    app_debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # --- Security ---
    secret_key: str = "change-this-in-development"
    access_token_expire_minutes: int = 60 * 24 * 7

    # --- Database (PostgreSQL + pgvector in deployment, SQLite for local dev) ---
    database_url: str = "sqlite:///./clinicai.db"

    # --- LLM provider: "azure" | "openai" | "groq" | "openrouter" ---
    llm_provider: str = "groq"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2025-04-01-preview"
    azure_openai_deployment: str = "gpt-5-mini"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    # --- OpenRouter (OpenAI-compatible aggregator; no embeddings API) ---
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    # Fallbacks tried in order when the primary returns a provider error
    # (free-tier upstreams are sometimes overloaded; keep the list current at
    # https://openrouter.ai/models?orderBy=pricing&q=:free).
    openrouter_fallback_models: list[str] = [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ]
    openrouter_site_url: str = "https://github.com/"
    openrouter_site_title: str = "Clinic AI Receptionist"

    # --- Embeddings (RAG) ---
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # --- WhatsApp (Meta Cloud API) ---
    whatsapp_waba_id: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_webhook_verify_token: str = ""
    # App Secret from the Meta app dashboard. When set, incoming webhooks MUST
    # carry a valid X-Hub-Signature-256 (HMAC-SHA256 of the raw body).
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v21.0"
    whatsapp_base_url: str = "https://graph.facebook.com"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
