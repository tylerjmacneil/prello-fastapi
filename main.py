# main.py
from __future__ import annotations

import os
import logging
import importlib
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Prello API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# ──────────────────────────────────────────────────────────────────────────────
# CORS (relaxed for now; tighten later)
# ──────────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # e.g. ["https://prello.app", "http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────────────
# Root + Health
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/", tags=["default"])
def read_root():
    return {"ok": True, "service": "prello-api"}

@app.get("/health/db", tags=["health"])
def health_db():
    """Ping Supabase using service role (set SUPABASE_URL & SUPABASE_SERVICE_ROLE in Railway)."""
    try:
        from supabase import create_client  # lazy import
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE")
        if not url or not key:
            raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE")
        client = create_client(url, key)
        resp = client.table("clients").select("id").limit(1).execute()
        if resp.error:
            raise RuntimeError(resp.error.message)
        return {"ok": True, "db": "up"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB check failed: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Dynamic router loader
# ──────────────────────────────────────────────────────────────────────────────
def include_router_dynamically(candidates: list[str], name: str) -> None:
    """
    Try multiple module paths until one works. Each module must expose a `router`.
    Logs failures but keeps the app up.
    """
    last_err: Optional[Exception] = None
    for module_path in candidates:
        try:
            mod = importlib.import_module(module_path)
            rtr = getattr(mod, "router")
            app.include_router(rtr)
            log.info(f"[main] Included router: {module_path} as {name}")
            return
        except Exception as e:
            last_err = e
            log.warning(f"[main] Failed to include {module_path}: {e}")
    log.error(f"[main] Could not include {name} router. Tried: {candidates}. Last error: {last_err}")

# Ensure `routers` is a package (create an empty routers/__init__.py if missing)
# Load routers from several likely locations based on your repo screenshot.
include_router_dynamically(
    ["routers.clients", "clients", "app.routers.clients", "app.clients"],
    name="clients",
)
include_router_dynamically(
    # You have payments.py at repo root; try that first
    ["payments", "routers.payments", "app.routers.payments", "app.payments"],
    name="payments",
)
include_router_dynamically(
    # You moved jobs to routers/jobs.py; this will pick it up
    ["routers.jobs", "jobs", "app.routers.jobs", "app.jobs"],
    name="jobs",
)

# ──────────────────────────────────────────────────────────────────────────────
# Local dev entrypoint
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
    )
