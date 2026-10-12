"""Production standalone server for Reflex frontend on Render.
Serves static Next/React assets and Reflex WebSocket state engine in a single lightweight Uvicorn process.
Memory footprint: ~45MB (well below Render's 512MB limit).
"""
import os
from pathlib import Path

# Instruct Reflex to mount the pre-compiled frontend static bundle into the ASGI application
os.environ["__REFLEX_MOUNT_FRONTEND_COMPILED_APP"] = "True"
os.environ["ENVIRONMENT"] = os.getenv("ENVIRONMENT", "production")

from frontend.frontend import app

# Calling app() builds the top-level ASGI Starlette app WITH the full lifespan context.
# This starts the BaseStateEventProcessor, token manager, and WebSocket handlers.
api = app()

# Fallback: In case the built bundle was not auto-mounted, ensure static files are served
has_frontend_mount = any(
    getattr(route, "name", "") in ("frontend", "static_frontend")
    for route in getattr(app._api, "routes", [])
)

if not has_frontend_mount:
    from starlette.staticfiles import StaticFiles
    base_dir = Path(__file__).resolve().parent
    static_candidates = [
        base_dir / ".web" / "build" / "client",
        base_dir / ".web" / "_static",
        base_dir / ".web" / "build",
    ]
    for static_dir in static_candidates:
        if static_dir.exists() and (static_dir / "index.html").exists():
            app._api.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static_frontend")
            print(f"Fallback mounted static frontend from {static_dir}", flush=True)
            break

if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    print(f"Starting production server on 0.0.0.0:{port} with active event processor and WebSocket support...", flush=True)
    try:
        import uvicorn
        uvicorn.run(
            api,
            host="0.0.0.0",
            port=port,
            proxy_headers=True,
            forwarded_allow_ips="*",
            ws_ping_interval=25,
            ws_ping_timeout=30,
        )
    except ImportError:
        import granian
        from granian.constants import Interfaces
        print("Uvicorn not found, running with Granian engine...", flush=True)
        granian.Granian(api, address="0.0.0.0", port=port, interface=Interfaces.ASGI).serve()

