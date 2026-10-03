"""Endpoints for Human-in-the-loop Insight Feedback (Plan §8.6)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from backend.app.api.deps import get_optional_current_user
from backend.app.core.database import get_db
from backend.app.models.feedback import InsightFeedback
from backend.app.models.job import AnalysisJob
from backend.app.models.user import User

router = APIRouter()

class FeedbackCreateRequest(BaseModel):
    rating: str  # "helpful" | "not_relevant"
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("helpful", "not_relevant"):
            raise ValueError("Rating must be either 'helpful' or 'not_relevant'")
        return v

class FeedbackResponse(BaseModel):
    id: str
    job_id: str
    insight_id: str
    user_id: Optional[str]
    rating: str
    comment: Optional[str]
    created_at: datetime

class InsightFeedbackSummary(BaseModel):
    insight_id: str
    total_feedbacks: int
    helpful_count: int
    not_relevant_count: int
    feedbacks: List[FeedbackResponse]

@router.post("/jobs/{job_id}/insights/{insight_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_insight_feedback(
    job_id: str,
    insight_id: str,
    req: FeedbackCreateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Submit rating and optional feedback for an analysis insight."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job {job_id} not found."
        )

    feedback = InsightFeedback(
        job_id=job_id,
        insight_id=insight_id,
        user_id=current_user.id if current_user else None,
        rating=req.rating,
        comment=req.comment
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return FeedbackResponse(
        id=feedback.id,
        job_id=feedback.job_id,
        insight_id=feedback.insight_id,
        user_id=feedback.user_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at
    )

@router.get("/jobs/{job_id}/insights/{insight_id}/feedback", response_model=InsightFeedbackSummary)
def get_insight_feedback(
    job_id: str,
    insight_id: str,
    db: Session = Depends(get_db)
):
    """Retrieve all feedbacks and summary ratings for an insight."""
    items = db.query(InsightFeedback).filter(
        InsightFeedback.job_id == job_id,
        InsightFeedback.insight_id == insight_id
    ).order_by(InsightFeedback.created_at.desc()).all()

    helpful = sum(1 for item in items if item.rating == "helpful")
    not_relevant = sum(1 for item in items if item.rating == "not_relevant")

    return InsightFeedbackSummary(
        insight_id=insight_id,
        total_feedbacks=len(items),
        helpful_count=helpful,
        not_relevant_count=not_relevant,
        feedbacks=[
            FeedbackResponse(
                id=item.id,
                job_id=item.job_id,
                insight_id=item.insight_id,
                user_id=item.user_id,
                rating=item.rating,
                comment=item.comment,
                created_at=item.created_at
            )
            for item in items
        ]
    )
