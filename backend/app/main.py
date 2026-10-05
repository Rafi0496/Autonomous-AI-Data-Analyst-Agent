"""FastAPI main application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.v1.api import api_router
from backend.app.core.config import settings
from backend.app.core.config_validator import validate_startup_config
from backend.app.core.database import init_db
from backend.app.core.logging_middleware import RequestLoggingMiddleware, register_error_handlers

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate config and ensure migrations run
    validate_startup_config()
    init_db()
    yield
    # Shutdown logic if any

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Autonomous AI Data Analyst Agent Backend API — Data ingestion, cleaning, profiling, and autonomous agent orchestration.",
    version="0.1.0",
    lifespan=lifespan
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup structured logging with request IDs
app.add_middleware(RequestLoggingMiddleware)

# Setup uniform JSON error handlers
register_error_handlers(app)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)



@app.get("/health")
def health_check():
    return {"status": "ok", "service": "backend"}

@app.get("/")
def root():
    return {
        "message": "Welcome to the Autonomous AI Data Analyst Agent API",
        "docs_url": "/docs",
        "health_url": f"{settings.API_V1_STR}/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
