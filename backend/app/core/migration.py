"""Idempotent database migration supporting SQLite and PostgreSQL syntax.

Ensures all required tables and columns exist across releases,
and assigns legacy rows lacking an owner to a default system user.
"""
import logging
from typing import List, Set
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from backend.app.core.security import hash_password

logger = logging.getLogger(__name__)

DEFAULT_LEGACY_USER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_LEGACY_USER_EMAIL = "legacy_system_user@local.internal"

def run_migrations(engine: Engine) -> None:
    """Run idempotent migrations on the provided database engine."""
    from backend.app.core.database import Base
    import backend.app.models.dataset
    import backend.app.models.user
    import backend.app.models.job
    import backend.app.models.feedback
    import backend.app.models.schedule

    # 1. Create any missing tables from declarative models
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    is_sqlite = engine.dialect.name == "sqlite"

    with engine.begin() as conn:
        # 2. Check and migrate `datasets` table
        if "datasets" in existing_tables:
            cols = {c["name"] for c in inspector.get_columns("datasets")}
            if "user_id" not in cols:
                conn.execute(text("ALTER TABLE datasets ADD COLUMN user_id VARCHAR(36)"))
            if "is_sampled" not in cols:
                default_val = "0" if is_sqlite else "FALSE"
                conn.execute(text(f"ALTER TABLE datasets ADD COLUMN is_sampled BOOLEAN DEFAULT {default_val}"))
            if "original_row_count" not in cols:
                conn.execute(text("ALTER TABLE datasets ADD COLUMN original_row_count INTEGER"))
            if "sampling_rate" not in cols:
                conn.execute(text("ALTER TABLE datasets ADD COLUMN sampling_rate FLOAT"))

        # 3. Check and migrate `analysis_jobs` table
        if "analysis_jobs" in existing_tables:
            cols = {c["name"] for c in inspector.get_columns("analysis_jobs")}
            if "user_id" not in cols:
                conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN user_id VARCHAR(36)"))
            if "current_step" not in cols:
                conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN current_step INTEGER DEFAULT 0"))
            if "phase" not in cols:
                conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN phase VARCHAR(50) DEFAULT 'queued'"))
            if "execution_time_seconds" not in cols:
                conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN execution_time_seconds FLOAT DEFAULT 0.0"))
            if "verification" not in cols:
                conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN verification TEXT"))

        # 4. Check and migrate `insight_feedback` table
        if "insight_feedback" in existing_tables:
            cols = {c["name"] for c in inspector.get_columns("insight_feedback")}
            if "user_id" not in cols:
                conn.execute(text("ALTER TABLE insight_feedback ADD COLUMN user_id VARCHAR(36)"))

        # 5. Check and migrate `analysis_schedules` table
        if "analysis_schedules" in existing_tables:
            cols = {c["name"] for c in inspector.get_columns("analysis_schedules")}
            if "user_id" not in cols:
                conn.execute(text("ALTER TABLE analysis_schedules ADD COLUMN user_id VARCHAR(36)"))

        # 6. Ensure default system user exists for legacy unassigned rows
        user_exists = conn.execute(
            text("SELECT id FROM users WHERE id = :uid OR email = :email"),
            {"uid": DEFAULT_LEGACY_USER_ID, "email": DEFAULT_LEGACY_USER_EMAIL}
        ).fetchone()

        if not user_exists:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, hashed_password, full_name, is_active, created_at) "
                    "VALUES (:id, :email, :pw, :name, :active, CURRENT_TIMESTAMP)"
                ),
                {
                    "id": DEFAULT_LEGACY_USER_ID,
                    "email": DEFAULT_LEGACY_USER_EMAIL,
                    "pw": hash_password("LegacySystemUserDisabledPassword!123"),
                    "name": "Legacy System User",
                    "active": True
                }
            )


        # 7. Assign unassigned legacy rows to default user
        if "datasets" in existing_tables:
            conn.execute(
                text("UPDATE datasets SET user_id = :uid WHERE user_id IS NULL"),
                {"uid": DEFAULT_LEGACY_USER_ID}
            )
        if "analysis_jobs" in existing_tables:
            conn.execute(
                text("UPDATE analysis_jobs SET user_id = :uid WHERE user_id IS NULL"),
                {"uid": DEFAULT_LEGACY_USER_ID}
            )
        if "analysis_schedules" in existing_tables:
            conn.execute(
                text("UPDATE analysis_schedules SET user_id = :uid WHERE user_id IS NULL"),
                {"uid": DEFAULT_LEGACY_USER_ID}
            )
        if "insight_feedback" in existing_tables:
            conn.execute(
                text("UPDATE insight_feedback SET user_id = :uid WHERE user_id IS NULL"),
                {"uid": DEFAULT_LEGACY_USER_ID}
            )

    logger.info("Database migration completed successfully.")
