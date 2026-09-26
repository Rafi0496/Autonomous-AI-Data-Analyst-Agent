"""FastAPI v1 API router aggregation."""
from fastapi import APIRouter
from backend.app.api.v1.endpoints import datasets, health, upload

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(upload.router, tags=["Upload"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
