from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db import get_session

router = APIRouter()

class ClientCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

def require_user_id(x_user_id: Optional[str] = Header(default=None, alias="X-User-Id")) -> str:
    """
    TEMP: accept a user id via header. We'll switch to real Supabase JWT next.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    return x_user_id

@router.get("/")
async def list_clients(
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(require_user_id),
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
    user_id: str = Depends(require_user_id),
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

