"""SQLAlchemy model for Analysis Jobs and Execution Traces."""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Column, DateTime, Integer, String, Text
from backend.app.core.database import Base

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    dataset_id = Column(String(36), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, running, completed, budget_tripped, failed
    current_step_name = Column(String(100), nullable=False, default="queued")
    goal = Column(String(500), nullable=True)
    
    # Budgets and Resource Tracking
    total_steps = Column(Integer, default=0)
    step_limit = Column(Integer, default=6)
    tokens_used = Column(Integer, default=0)
    token_budget = Column(Integer, default=15000)
    execution_time_seconds = Column(Integer, default=0)

    # Persisted JSON Artifacts
    run_log_json = Column(Text, nullable=True)        # Ordered list of execution steps (explainability)
    results_json = Column(Text, nullable=True)        # Executive summary, findings, and chart specs
    verification_json = Column(Text, nullable=True)   # Citation checker audit result

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def get_run_log(self) -> List[Dict[str, Any]]:
        if self.run_log_json:
            return json.loads(self.run_log_json)
        return []

    def set_run_log(self, logs: List[Dict[str, Any]]):
        self.run_log_json = json.dumps(logs)

    def get_results(self) -> Optional[Dict[str, Any]]:
        if self.results_json:
            return json.loads(self.results_json)
        return None

    def set_results(self, res: Dict[str, Any]):
        self.results_json = json.dumps(res)

    def get_verification(self) -> Optional[Dict[str, Any]]:
        if self.verification_json:
            return json.loads(self.verification_json)
        return None

    def set_verification(self, ver: Dict[str, Any]):
        self.verification_json = json.dumps(ver)

    def get_insights(self) -> List[Dict[str, Any]]:
        res = self.get_results()
        if res and isinstance(res, dict) and "insights" in res:
            return res["insights"]
        return []

    def set_insights(self, insights: List[Dict[str, Any]]):
        res = self.get_results() or {}
        res["insights"] = insights
        self.set_results(res)
