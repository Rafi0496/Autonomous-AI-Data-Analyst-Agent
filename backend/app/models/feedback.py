"""SQLAlchemy model for Insight Feedback (Plan §8.6 Human-in-the-loop)."""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, String, Text
from backend.app.core.database import Base

class InsightFeedback(Base):
    __tablename__ = "insight_feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    job_id = Column(String(36), nullable=False, index=True)
    insight_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    rating = Column(String(20), nullable=False)  # "helpful" | "not_relevant"
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
