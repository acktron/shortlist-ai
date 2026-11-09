from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://shortlist:shortlist@localhost:5432/shortlist"
    test_database_url: str = "postgresql+psycopg://shortlist:shortlist@localhost:5432/shortlist_test"
    jwt_secret: str = "dev-only-change-me"; jwt_expires_min: int = 60
    ai_mode: str = "mock"; ai_concurrency: int = 2
    ollama_base_url: str = "http://localhost:11434"; ollama_model: str = "qwen2.5:7b"; ollama_vision_model: str = "qwen2.5vl:7b"
    gemini_api_key: str = ""; gemini_model: str = "gemini-2.0-flash"; cors_origins: str = "http://localhost:5173"; max_upload_mb: int = 10; max_batch_files: int = 500
    model_config = SettingsConfigDict(env_file=("backend/.env", ".env", "../.env"), extra="ignore")
settings = Settings()

