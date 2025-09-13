from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db import get_session

router = APIRouter()

class ClientCreate(BaseModel):
    name: str
    email: Optional[str] = None   # keep simple (no extra deps)
    phone: Optional[str] = None
    address: Optional[str] = None

@router.get("/")
async def list_clients(db: AsyncSession = Depends(get_session)):
    result = await db.execute(text(
        "select id, name, email, phone, address, created_at from public.clients order by created_at desc"
    ))
    return [dict(row) for row in result.mappings().all()]

@router.post("/")
async def create_client(payload: ClientCreate, db: AsyncSession = Depends(get_session)):
    q = text("""
        insert into public.clients (name, email, phone, address)
        values (:name, :email, :phone, :address)
        returning id, name, email, phone, address, created_at
    """)
    result = await db.execute(q, payload.model_dump())
    await db.commit()
    return dict(result.mappings().first())

