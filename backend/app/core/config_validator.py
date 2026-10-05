"""Startup configuration validation with clear messages for missing required variables (Plan M6)."""
import os
import sys
from pathlib import Path
from backend.app.core.config import settings

def validate_startup_config() -> None:
    """Validate all required environment and application configuration at startup."""
    errors = []

    # 1. Database validation
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is missing or empty. Please specify a valid database connection string.")

    # 2. Environment & Security validation
    env = settings.ENVIRONMENT.lower()
    if env not in ("dev", "test", "development"):
        if settings.JWT_SECRET == settings.DEFAULT_DEV_SECRET:
            errors.append(
                f"In production/staging environment ('{settings.ENVIRONMENT}'), JWT_SECRET must be set via "
                f"environment variable to a strong random key and cannot use the default dev secret."
            )
        if len(settings.JWT_SECRET) < 16:
            errors.append("JWT_SECRET must be at least 16 characters long.")

    # 3. LLM Provider validation
    valid_providers = ("claude", "gemini", "heuristic", "mock")
    if settings.LLM_PROVIDER.lower() not in valid_providers:
        errors.append(
            f"Invalid LLM_PROVIDER '{settings.LLM_PROVIDER}'. Must be one of: {', '.join(valid_providers)}"
        )
    
    # In live environments, ensure API keys are present for chosen provider
    if env in ("production", "staging", "prod"):
        if settings.LLM_PROVIDER.lower() == "claude" and not settings.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required when LLM_PROVIDER is 'claude' in production.")
        elif settings.LLM_PROVIDER.lower() == "gemini" and not settings.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required when LLM_PROVIDER is 'gemini' in production.")

    # 4. Storage directory writability
    for dir_name, dir_path in [
        ("UPLOAD_DIR", settings.UPLOAD_DIR),
        ("PROCESSED_DIR", settings.PROCESSED_DIR),
        ("SAMPLES_DIR", settings.SAMPLES_DIR),
        ("REPORTS_DIR", settings.REPORTS_DIR)
    ]:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = dir_path / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
        except Exception as e:
            errors.append(f"Storage directory {dir_name} ('{dir_path}') is not writable: {str(e)}")

    if errors:
        error_msg = "Startup configuration validation failed:\n  - " + "\n  - ".join(errors)
        raise ValueError(error_msg)
