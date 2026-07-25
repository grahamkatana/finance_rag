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

    # Ollama
    ollama_base_url: str
    ollama_llm_model: str
    ollama_embed_model: str
    ollama_judge_model: str

    #Embedding 
    embedding_size: int

    # App
    app_env: str
    app_port: int

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
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