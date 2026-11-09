from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    env: str = "development"
    database_url: str = "postgresql+psycopg://shortlist:shortlist@localhost:5432/shortlist"
    test_database_url: str = "postgresql+psycopg://shortlist:shortlist@localhost:5432/shortlist_test"
    jwt_secret: str = "dev-only-change-me"; jwt_expires_min: int = 60
    ai_mode: str = "mock"; ai_concurrency: int = 2
    ollama_base_url: str = "http://localhost:11434"; ollama_model: str = "qwen2.5:7b"; ollama_vision_model: str = "qwen2.5vl:7b"
    gemini_api_key: str = ""; gemini_model: str = "gemini-2.5-flash"; cors_origins: str = "http://localhost:5173"; max_upload_mb: int = 10; max_batch_files: int = 500
    gemini_request_interval_seconds: float = 0
    model_config = SettingsConfigDict(env_file=("backend/.env", ".env", "../.env"), extra="ignore")

    @model_validator(mode="after")
    def require_production_jwt_secret(self):
        if self.env.casefold() == "production" and (
            not self.jwt_secret.strip() or self.jwt_secret == "dev-only-change-me"
        ):
            raise ValueError("JWT_SECRET must be set to a non-development value when ENV=production.")
        return self


settings = Settings()

