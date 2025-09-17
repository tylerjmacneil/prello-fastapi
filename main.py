# main.py
from __future__ import annotations

import os
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client, Client

log = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Prello API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# ──────────────────────────────────────────────────────────────────────────────
# CORS (relaxed for now; tighten to your domains later)
# ──────────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        client = _get_supabase()
        resp = client.table("clients").select("id").limit(1).execute()
        if resp.error:
            raise RuntimeError(resp.error.message)
        return {"ok": True, "db": "up"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB check failed: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Diagnostics (to explain 500s quickly)
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/diag", tags=["health"])
def diag():
    out = {
        "supabase_url_set": bool(os.environ.get("SUPABASE_URL")),
        "service_role_set": bool(os.environ.get("SUPABASE_SERVICE_ROLE")),
        "errors": [],
    }
    try:
        client = _get_supabase()
    except Exception as e:
        out["errors"].append(f"supabase init: {e}")
        return out

    checks = {
        "clients": "id,name,email,phone,address,created_at",
        "jobs":    "id,client_id,title,description,price_cents,status,created_at",
    }
    for table, cols in checks.items():
        try:
            resp = client.table(table).select(cols).limit(1).execute()
            if resp.error:
                out["errors"].append(f"{table} select error: {resp.error.message}")
        except Exception as e:
            out["errors"].append(f"{table} select exception: {e}")

    return out

# ──────────────────────────────────────────────────────────────────────────────
# Supabase helper
# ──────────────────────────────────────────────────────────────────────────────
def _get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE")
    return create_client(url, key)

# ──────────────────────────────────────────────────────────────────────────────
# Models (emails as plain strings to avoid extra dependency)
# ──────────────────────────────────────────────────────────────────────────────
class ApiClient(BaseModel):
    id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None

class ApiJob(BaseModel):
    id: UUID
    client_id: UUID
    title: str
    description: Optional[str] = None
    price_cents: int
    status: str
    created_at: Optional[datetime] = None
    client: Optional[ApiClient] = None

class JobCreate(BaseModel):
    client_name: str = Field(..., min_length=1)
    client_email: Optional[str] = None
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    price_cents: int = Field(..., ge=0)

def _row_to_client(row: Dict[str, Any]) -> ApiClient:
    return ApiClient(
        id=row["id"],
        name=row["name"],
        email=row.get("email"),
        phone=row.get("phone"),
        address=row.get("address"),
        created_at=row.get("created_at"),
    )

def _row_to_job(row: Dict[str, Any]) -> ApiJob:
    client = _row_to_client(row["client"]) if isinstance(row.get("client"), dict) else None
    return ApiJob(
        id=row["id"],
        client_id=row["client_id"],
        title=row["title"],
        description=row.get("description"),
        price_cents=row["price_cents"],
        status=row["status"],
        created_at=row.get("created_at"),
        client=client,
    )

# ──────────────────────────────────────────────────────────────────────────────
# Jobs endpoints (inline so they ALWAYS appear in Swagger)
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/jobs/", tags=["jobs"], response_model=List[ApiJob])
def list_jobs():
    try:
        client = _get_supabase()
        resp = (
            client.table("jobs")
            .select("id,client_id,title,description,price_cents,status,created_at,client:clients(id,name,email,phone,address,created_at)")
            .order("created_at", desc=True)
            .execute()
        )
        if resp.error:
            raise HTTPException(status_code=500, detail=f"jobs select error: {resp.error.message}")
        rows = resp.data or []
        return [_row_to_job(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/jobs/ GET failed: {e}")

@app.post("/jobs/", tags=["jobs"], response_model=ApiJob)
def create_job(payload: JobCreate):
    try:
        client = _get_supabase()

        # 1) find or create client by name (simple upsert)
        existing = (
            client.table("clients")
            .select("id,name,email,phone,address,created_at")
            .eq("name", payload.client_name)
            .limit(1)
            .execute()
        )
        if existing.error:
            raise HTTPException(status_code=500, detail=f"clients select error: {existing.error.message}")

        if existing.data:
            client_row = existing.data[0]
        else:
            ins_client = (
                client.table("clients")
                .insert({"name": payload.client_name, "email": payload.client_email})
                .select("id,name,email,phone,address,created_at")
                .single()
                .execute()
            )
            if ins_client.error:
                raise HTTPException(status_code=500, detail=f"clients insert error: {ins_client.error.message}")
            client_row = ins_client.data

        # 2) insert job
        ins_job = (
            client.table("jobs")
            .insert({
                "client_id": client_row["id"],
                "title": payload.title,
                "description": payload.description,
                "price_cents": payload.price_cents,
                "status": "active_unscheduled",
            })
            .select("id,client_id,title,description,price_cents,status,created_at")
            .single()
            .execute()
        )
        if ins_job.error:
            raise HTTPException(status_code=500, detail=f"jobs insert error: {ins_job.error.message}")

        job_row = ins_job.data
        job_row["client"] = client_row
        return _row_to_job(job_row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/jobs/ POST failed: {e}")

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

