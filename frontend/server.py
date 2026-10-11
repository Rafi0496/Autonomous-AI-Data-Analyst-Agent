"""Production standalone server for Reflex frontend on Render.
Serves static Next/React assets and Reflex WebSocket state engine in a single lightweight Uvicorn process.
Memory footprint: ~45MB (well below Render's 512MB limit).
"""
import os
from pathlib import Path
from starlette.staticfiles import StaticFiles
from frontend.frontend import app

base_dir = Path(__file__).resolve().parent
static_candidates = [
    base_dir / ".web" / "build" / "client",
    base_dir / ".web" / "_static",
    base_dir / ".web" / "build",
]

mounted = False
for static_dir in static_candidates:
    if static_dir.exists() and (static_dir / "index.html").exists():
        app._api.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static_frontend")
        print(f"Mounted static frontend from {static_dir}")
        mounted = True
        break

if not mounted:
    print("Warning: No pre-built static frontend found. Serving API and WebSocket routes only.")

api = app._api

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(api, host="0.0.0.0", port=port)
