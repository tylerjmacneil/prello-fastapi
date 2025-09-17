# routers/jobs.py
from __future__ import annotations

import os
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, EmailStr
from supabase import create_client, Client

# ---- Supabase service client (use service_role on the server) ----
def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE")
    return create_client(url, key)

# IMPORTANT: prefix '/jobs' → paths will be '/jobs/' etc.
router = APIRouter(prefix="/jobs", tags=["jobs"])

# ---- Schemas (match your iOS ApiJob / ApiClient) ----
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

# GET /jobs/
@router.get("/", response_model=List[ApiJob])
def list_jobs(supabase: Client = Depends(get_supabase)):
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

# POST /jobs/
@router.post("/", response_model=ApiJob)
def create_job(payload: JobCreate, supabase: Client = Depends(get_supabase)):
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
        inserted = (
            supabase.table("clients")
            .insert({"name": payload.client_name, "email": payload.client_email})
            .select("id,name,email,phone,address,created_at")
            .single()
            .execute()
        )
        if inserted.error:
            raise HTTPException(status_code=500, detail=inserted.error.message)
        client_row = inserted.data

    ins_job = (
        supabase.table("jobs")
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
        raise HTTPException(status_code=500, detail=ins_job.error.message)

    job_row = ins_job.data
    job_row["client"] = client_row
    return _row_to_job(job_row)
