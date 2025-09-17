# routers/jobs.py
from __future__ import annotations

from typing import Optional, List, Any, Dict
from uuid import UUID
from datetime import datetime
import os

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, EmailStr
from supabase import create_client, Client

# ──────────────────────────────────────────────────────────────────────────────
# Supabase client (service role so it bypasses RLS on the server)
# Set env vars in Railway:
#   SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
#   SUPABASE_SERVICE_ROLE=eyJhbGciOiJI...  (service role key)
# ──────────────────────────────────────────────────────────────────────────────
def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE")
    return create_client(url, key)

router = APIRouter(prefix="/jobs", tags=["jobs"])

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic models (shape matches your iOS ApiJob / ApiClient)
# ──────────────────────────────────────────────────────────────────────────────
class ApiClient(BaseModel):
    id: UUID
    name: str
    email: Optional[EmailStr] = None
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
    client_email: Optional[EmailStr] = None
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    price_cents: int = Field(..., ge=0)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
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
    # When using PostgREST joins, the embedded relation will be under the alias "client"
    client = None
    if isinstance(row.get("client"), dict):
        client = _row_to_client(row["client"])

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
# GET /jobs/  — list jobs (newest first) with embedded client
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/", response_model=List[ApiJob])
def list_jobs(supabase: Client = Depends(get_supabase)):
    # Join syntax: select("..., client:clients(*)") where jobs.client_id -> clients.id
    resp = (
        supabase.table("jobs")
        .select("id,client_id,title,description,price_cents,status,created_at,client:clients(id,name,email,phone,address,created_at)")
        .order("created_at", desc=True)
        .execute()
    )
    if resp.error:
        raise HTTPException(status_code=500, detail=resp.error.message)

    rows = resp.data or []
    return [_row_to_job(r) for r in rows]

# ──────────────────────────────────────────────────────────────────────────────
# POST /jobs/ — create client (upsert-by-name) if needed, then create job
# returns the created job with embedded client
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/", response_model=ApiJob)
def create_job(payload: JobCreate, supabase: Client = Depends(get_supabase)):
    # 1) Find or create client (simple upsert by name; tweak as you prefer)
    existing = (
        supabase.table("clients")
        .select("id,name,email,phone,address,created_at")
        .eq("name", payload.client_name)
        .limit(1)
        .execute()
    )
    if existing.error:
        raise HTTPException(status_code=500, detail=existing.error.message)

    if existing.data:
        client_row = existing.data[0]
    else:
        insert_client = (
            supabase.table("clients")
            .insert(
                {
                    "name": payload.client_name,
                    "email": payload.client_email,
                }
            )
            .select("id,name,email,phone,address,created_at")
            .single()
            .execute()
        )
        if insert_client.error:
            raise HTTPException(status_code=500, detail=insert_client.error.message)
        client_row = insert_client.data

    client_id = client_row["id"]

    # 2) Insert job
    insert_job = (
        supabase.table("jobs")
        .insert(
            {
                "client_id": client_id,
                "title": payload.title,
                "description": payload.description,
                "price_cents": payload.price_cents,
                "status": "active_unscheduled",
            }
        )
        .select("id,client_id,title,description,price_cents,status,created_at")
        .single()
        .execute()
    )
    if insert_job.error:
        raise HTTPException(status_code=500, detail=insert_job.error.message)

    job_row = insert_job.data

    # 3) Return job with embedded client
    job_row["client"] = client_row
    return _row_to_job(job_row)
