from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_session
from app.auth import verify_and_get_user_id

router = APIRouter()

class ClientCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

@router.get("/")
async def list_clients(
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(verify_and_get_user_id),
):
    result = await db.execute(text("""
        select id, name, email, phone, address, created_at
        from public.clients
        where user_id = :uid
        order by created_at desc
    """), {"uid": user_id})
    return [dict(row) for row in result.mappings().all()]

@router.post("/")
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(verify_and_get_user_id),
):
    q = text("""
        insert into public.clients (name, email, phone, address, user_id)
        values (:name, :email, :phone, :address, :uid)
        returning id, name, email, phone, address, created_at
    """)
    params = payload.model_dump()
    params["uid"] = user_id
    result = await db.execute(q, params)
    await db.commit()
    return dict(result.mappings().first())

