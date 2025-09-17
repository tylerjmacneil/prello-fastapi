# main.py
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ──────────────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Prello API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# CORS (relax for now; tighten when you have fixed app domains)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # e.g., ["https://prello.app", "http://localhost:5173"]
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
    """
    Quick DB health check using Supabase service role.
    Set env in Railway:
      SUPABASE_URL, SUPABASE_SERVICE_ROLE
    """
    try:
        from supabase import create_client  # lazy import to avoid startup error if not installed

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE")
        if not url or not key:
            raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE")

        client = create_client(url, key)
        # Cheap ping: select 1 row from clients (or any table you have)
        resp = client.table("clients").select("id").limit(1).execute()
        if resp.error:
            raise RuntimeError(resp.error.message)
        return {"ok": True, "db": "up"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB check failed: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────────────────────────────────────
# New Jobs router (you created this in routers/jobs.py)
try:
    from routers import jobs  # noqa: E402
    app.include_router(jobs.router)  # mounts at /jobs/
except Exception as e:
    # Don’t crash if the file isn’t present yet; still serve / and /health/db
    print(f"[main] jobs router not loaded: {e}")

# Optional: keep existing routers if you already have them
try:
    from routers import clients  # noqa: E402
    app.include_router(clients.router)  # e.g., /clients/
except Exception as e:
    print(f"[main] clients router not loaded: {e}")

try:
    from routers import payments  # noqa: E402
    app.include_router(payments.router)  # e.g., /payments/*
except Exception as e:
    print(f"[main] payments router not loaded: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Local dev entrypoint (Railway typically uses a Procfile / start command)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
    )
