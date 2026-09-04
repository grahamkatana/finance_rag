from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int

    # Qdrant
    qdrant_host: str
    qdrant_port: int
    qdrant_collection: str

    # Generation
    llm_provider: str = "ollama"
    llm_model: str = "phi4-mini"
    llm_base_url: str = "http://localhost:11434"
    llm_api_key: str = ""

    # Embeddings
    embed_provider: str = "ollama"
    embed_model: str = "nomic-embed-text"
    embed_base_url: str = "http://localhost:11434"
    embed_api_key: str = ""
    embedding_size: int = 768

    # Eval judge
    judge_provider: str = "ollama"
    judge_model: str = "gemma3:4b"
    judge_base_url: str = "http://localhost:11434"
    judge_api_key: str = ""

    # Redis
    redis_url: str

    # JWT Auth
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Admin seed (optional — creates admin on first startup if set)
    admin_email: str = ""
    admin_username: str = ""
    admin_password: str = ""

    # App
    app_env: str
    app_port: int

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}"
            f":{self.postgres_password}"
            f"@{self.postgres_host}"
            f":{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def postgres_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}"
            f":{self.postgres_password}"
            f"@{self.postgres_host}"
            f":{self.postgres_port}"
            f"/{self.postgres_db}"
        )


settings = Settings()
