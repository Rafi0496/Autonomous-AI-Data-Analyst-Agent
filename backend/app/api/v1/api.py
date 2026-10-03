"""FastAPI v1 API router aggregation."""
from fastapi import APIRouter
from backend.app.api.v1.endpoints import auth, chat, datasets, feedback, health, jobs, reports, schedules, upload

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(upload.router, tags=["Upload"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(feedback.router, tags=["Feedback"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["Schedules"])
