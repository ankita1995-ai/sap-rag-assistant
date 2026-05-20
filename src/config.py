from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Google Gemini
    google_api_key: str
    google_model: str = "gemini-2.5-flash-lite"
    google_embedding_model: str = "models/gemini-embedding-001"

    # Vector store
    faiss_index_path: str = "./data/faiss_index"

    # Chunking strategy
    chunk_size: int = 512
    chunk_overlap: int = 100

    # Retrieval
    max_retrieval_docs: int = 4

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (reads from .env once)."""
    return Settings()
