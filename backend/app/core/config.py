from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "NEXUS AI Evidence Intelligence Workspace"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/nexus"

    # Storage
    storage_root: str = "./storage"

    # LLM provider (stub — wired in Sprint 3+)
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""

    # Embeddings provider (stub — wired in Sprint 3+)
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = ""
    embedding_dimension: int = 1536


settings = Settings()
