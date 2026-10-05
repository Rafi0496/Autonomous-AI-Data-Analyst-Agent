"""Structured logging middleware and consistent JSON error handlers (Plan M6)."""
import http.client
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.requests")

# Context variable to hold request_id across async calls
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id_ctx", default=None)

def get_request_id() -> Optional[str]:
    return request_id_ctx.get()

def status_code_to_error_code(status_code: int) -> str:
    name = http.client.responses.get(status_code, "ERROR")
    clean_name = name.upper().replace(" ", "_").replace("'", "")
    return f"HTTP_{status_code}_{clean_name}"

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = req_id
        token = request_id_ctx.set(req_id)
        start_time = time.time()

        try:
            response = await call_next(request)
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = req_id
            
            logger.info(
                f"[{req_id}] {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms}ms)"
            )
            return response
        finally:
            request_id_ctx.reset(token)

def register_error_handlers(app: FastAPI) -> None:
    """Register uniform JSON error handlers matching M6 error schema."""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None) or get_request_id()
        error_code = status_code_to_error_code(exc.status_code)
        msg = str(exc.detail) if exc.detail else "An error occurred."
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error_code,
                "message": msg,
                "details": exc.detail,
                "detail": exc.detail,  # backward compatibility for existing tests
                "request_id": req_id
            },
            headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(RequestValidationError)

    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None) or get_request_id()
        safe_errors = jsonable_encoder(exc.errors())
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Input validation failed.",
                "details": safe_errors,
                "detail": safe_errors,  # backward compatibility for existing tests
                "request_id": req_id
            }
        )


    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None) or get_request_id()
        logger.exception(f"[{req_id}] Unhandled server exception on {request.method} {request.url.path}: {str(exc)}")
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "details": "Internal server error occurred. Check server logs.",
                "detail": "An internal server error occurred.",
                "request_id": req_id
            }
        )
