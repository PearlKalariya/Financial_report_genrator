from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Financial AI Agent"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    max_articles: int = 6
    demo_mode: bool = True
    google_api_key: str = ""
    tavily_api_key: str = ""
    serper_api_key: str = ""
    alpha_vantage_api_key: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    chroma_db_path: str = "./chroma_db"
    gemini_model: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("chroma_db_path", mode="before")
    @classmethod
    def default_chroma_path_when_blank(cls, value: str | None) -> str:
        if not value or not str(value).strip():
            return "./chroma_db"
        return str(value).strip()

    @field_validator("langfuse_host", mode="before")
    @classmethod
    def clean_langfuse_host(cls, value: str | None) -> str:
        if not value or not str(value).strip():
            return "https://cloud.langfuse.com"
        return str(value).strip()


settings = Settings()
