"""Application configuration using Pydantic Settings."""
import os
from pathlib import Path
from typing import List, Optional
from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Autonomous AI Data Analyst Agent"
    
    # LLM Provider settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "claude")
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5-5"
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    
    # Database settings
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "analyst_db")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    
    # Use SQLite as fallback if Postgres URL is not explicitly set
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
    )
    
    # Storage settings
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    SAMPLES_DIR: Path = BASE_DIR / "data" / "samples"
    REPORTS_DIR: Path = BASE_DIR / "data" / "reports"
    
    # Upload limits
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS: List[str] = [".csv"]  # CSV only per M5 (d)
    
    # Security & Auth
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev")
    ALLOW_ANONYMOUS: bool = os.getenv("ALLOW_ANONYMOUS", "false").lower() in ("true", "1", "yes")
    DEFAULT_DEV_SECRET: str = "autonomous-data-analyst-super-secret-key-2026"
    JWT_SECRET: str = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "autonomous-data-analyst-super-secret-key-2026"))
    SECRET_KEY: str = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "autonomous-data-analyst-super-secret-key-2026"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    MIN_PASSWORD_LENGTH: int = 8
    PBKDF2_ITERATIONS: int = 600_000
    
    # Scale Handling & Sampling (Plan §8.7)
    MAX_ROW_COUNT_LIMIT: int = 100_000
    SAMPLE_THRESHOLD_ROWS: int = int(os.getenv("SAMPLE_THRESHOLD_ROWS", "25000"))
    SAMPLE_SIZE_ROWS: int = int(os.getenv("SAMPLE_SIZE_ROWS", "10000"))
    
    # CORS (Restricted to configured origins per M5 (d))
    BACKEND_CORS_ORIGINS: List[str] = [
        o.strip() for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
        ).split(",") if o.strip()
    ]

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> "Settings":
        if self.ENVIRONMENT.lower() not in ("dev", "test", "development") and self.JWT_SECRET == self.DEFAULT_DEV_SECRET:
            if self.SECRET_KEY and self.SECRET_KEY != self.DEFAULT_DEV_SECRET:
                self.JWT_SECRET = self.SECRET_KEY
            else:
                import secrets
                import logging
                logging.getLogger(__name__).warning(
                    "JWT_SECRET not set in production. Generating an ephemeral cryptographic secret for this process session."
                )
                ephemeral_key = secrets.token_urlsafe(32)
                self.JWT_SECRET = ephemeral_key
                self.SECRET_KEY = ephemeral_key
        return self

settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
settings.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

