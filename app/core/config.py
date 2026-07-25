from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Hemoglobin AI API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "hemoglobin_ai"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    map_provider: str = "none"
    mapbox_access_token: str | None = None
    google_maps_api_key: str | None = None
    map_geocoding_provider: str = "google"
    map_visual_provider: str = "mapbox"
    pinecone_api_key: str | None = None
    pinecone_index_name: str | None = None
    pinecone_index_host: str | None = None
    pinecone_namespace: str = "hemoglobin-knowledge"
    openai_embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
