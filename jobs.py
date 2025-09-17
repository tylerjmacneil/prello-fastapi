from fastapi import APIRouter, Depends
from pydantic import BaseModel
from uuid import UUID
from typing import Optional
import supabase

router = APIRouter(prefix="/jobs", tags=["jobs"])

class JobCreate(BaseModel):
    client_name: str
    client_email: Optional[str]
    title: str
    description: Optional[str]
    price_cents: int

@router.get("/")
def list_jobs():
    # TODO: query supabase "jobs" table
    return []

@router.post("/")
def create_job(payload: JobCreate):
    # TODO: insert into supabase "jobs" table
    return {"job": payload}
