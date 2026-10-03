"""SQLAlchemy model for Scheduled Analysis (Phase 4 Automation)."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, String
from backend.app.core.database import Base

class AnalysisSchedule(Base):
    __tablename__ = "analysis_schedules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    dataset_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    frequency = Column(String(50), nullable=False, default="daily")  # "hourly", "daily", "weekly"
    goal = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_job_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
