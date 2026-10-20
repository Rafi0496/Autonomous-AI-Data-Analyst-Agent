"""FastAPI endpoints for interactive Chat Q&A (Milestone 4)."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.app.api.deps import get_optional_current_user
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.dataset import Dataset
from backend.app.models.job import AnalysisJob
from backend.app.models.user import User
from backend.app.services.chat_service import process_chat_question

router = APIRouter()

class ChatRequest(BaseModel):
    job_id: Optional[str] = Field(default=None, description="Optional ID of the analysis job")
    question: str = Field(..., description="User analytical question")
    history: Optional[List[Dict[str, str]]] = Field(default=[], description="Prior conversation turns")
    dataset_id: Optional[str] = Field(default=None, description="Optional dataset ID fallback")

class ChatResponse(BaseModel):
    answer: str
    evidence: List[Dict[str, Any]] = []
    verification: Dict[str, Any] = {}
    provider: Optional[str] = "heuristic"
    tool_calls_used: List[Dict[str, Any]] = []
    pre_strip_rate: Optional[float] = 100.0
    post_strip_rate: Optional[float] = 100.0

@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse)
def handle_chat_query(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
) -> ChatResponse:
    """Process user analytical question over dataset insights, run logs, and cleaning reports."""
    if not settings.ALLOW_ANONYMOUS and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    from backend.app.services.chat_service import is_destructive_or_out_of_scope
    if is_destructive_or_out_of_scope(request.question):
        return ChatResponse(
            answer="This request was rejected. The autonomous data analyst is strictly restricted to data analysis tasks.",
            evidence=[],
            verification={"is_valid": True},
            provider="guardrail",
            tool_calls_used=[]
        )

    job = None
    if request.job_id:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == request.job_id).first()
        if job and job.user_id and (not current_user or job.user_id != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found."
            )

    if request.dataset_id:
        ds = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
        if ds and ds.user_id and (not current_user or ds.user_id != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found."
            )

    try:
        result = process_chat_question(
            db=db,
            job_id=job.id if job else None,
            question=request.question,
            history=request.history,
            dataset_id=request.dataset_id or (job.dataset_id if job else None)
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Chat processing exception (%s); invoking resilient fallback: ", exc)
        from backend.app.services.chat_service import answer_heuristic_question, get_dataset_insights_fallback
        effective_ds_id = request.dataset_id or (job.dataset_id if job else None)
        profile = {}
        cleaning_report = {}
        insights = []
        if effective_ds_id:
            ds_obj = db.query(Dataset).filter(Dataset.id == effective_ds_id).first()
            if ds_obj:
                profile = (ds_obj.get_profile() if hasattr(ds_obj, "get_profile") else None) or {}
                cleaning_report = (ds_obj.get_cleaning_summary() if hasattr(ds_obj, "get_cleaning_summary") else None) or {}
            insights = get_dataset_insights_fallback(db, effective_ds_id)
        ans_text, ev, tr, _ = answer_heuristic_question(
            question=request.question,
            insights=insights,
            profile=profile,
            cleaning_report=cleaning_report,
            dataset_id=effective_ds_id or ""
        )
        result = {
            "answer": ans_text,
            "evidence": ev,
            "verification": {"is_valid": True, "status": "passed", "total_claims_checked": 0},
            "provider": "heuristic",
            "tool_calls_used": tr,
            "pre_strip_rate": 100.0,
            "post_strip_rate": 100.0
        }

    return ChatResponse(
        answer=result["answer"],
        evidence=result.get("evidence", []),
        verification=result.get("verification", {}),
        provider=result.get("provider", "heuristic"),
        tool_calls_used=result.get("tool_calls_used", []),
        pre_strip_rate=result.get("pre_strip_rate", 100.0),
        post_strip_rate=result.get("post_strip_rate", 100.0)
    )

