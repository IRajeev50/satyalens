from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    database_url: str = f"sqlite:///{ROOT / 'satyalens.db'}"
    google_factcheck_api_key: str | None = None
    llm_api_key: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    search_api_key: str | None = None
    search_provider: str | None = None
    ocr_api_key: str | None = None
    ocr_provider: str = "local_tesseract"
    max_upload_mb: int = 10
    c2pa_cli_path: str | None = None
    reverse_image_api_key: str | None = None
    reverse_image_provider: str | None = None
    forensics_api_key: str | None = None
    forensics_provider: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    translation_api_key: str | None = None
    translation_provider: str | None = None
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
