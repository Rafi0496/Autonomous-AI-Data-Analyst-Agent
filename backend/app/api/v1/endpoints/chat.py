"""FastAPI endpoints for interactive Chat Q&A (Milestone 4)."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.services.chat_service import process_chat_question

router = APIRouter()

class ChatRequest(BaseModel):
    job_id: str = Field(..., description="ID of the analysis job")
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
def handle_chat_query(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Process user analytical question over dataset insights, run logs, and cleaning reports."""
    result = process_chat_question(
        db=db,
        job_id=request.job_id,
        question=request.question,
        history=request.history,
        dataset_id=request.dataset_id
    )
    return ChatResponse(
        answer=result["answer"],
        evidence=result.get("evidence", []),
        verification=result.get("verification", {}),
        provider=result.get("provider", "heuristic"),
        tool_calls_used=result.get("tool_calls_used", []),
        pre_strip_rate=result.get("pre_strip_rate", 100.0),
        post_strip_rate=result.get("post_strip_rate", 100.0)
    )
