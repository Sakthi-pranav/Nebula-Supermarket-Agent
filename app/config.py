import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    TELEGRAM_BOT_TOKEN: str = ""
    
    # LLM Settings
    LLM_PROVIDER: str = "openai"  # openai, gemini, groq, custom
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str | None = None

    # Store Settings
    STORE_NAME: str = "Sharma General Supermarket"
    STORE_ADDRESS: str = "Shop 12, Main Market, Indiranagar, Bengaluru, KA - 560038"
    STORE_PHONE: str = "+91 98765 43210"
    STORE_GSTIN: str = "29ABCDE1234F1Z5"
    DEFAULT_PAYMENT_MODE: str = "UPI"

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/generated/supermarket.db"

    # Directories
    GENERATED_DIR: Path = BASE_DIR / "generated"
    INVOICE_DIR: Path = BASE_DIR / "generated" / "invoices"
    REPORT_DIR: Path = BASE_DIR / "generated" / "reports"

    def ensure_directories(self) -> None:
        """Ensure artifact directories exist."""
        self.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        self.INVOICE_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
