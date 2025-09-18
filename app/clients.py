# app/clients.py
from fastapi import APIRouter, Depends
from .deps import sb, get_user
from .models import ClientIn

router = APIRouter(prefix="/clients", tags=["clients"])

@router.get("")
async def list_clients(user = Depends(get_user)):
    r = sb.table("clients").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    return r.data

@router.post("")
async def create_client(payload: ClientIn, user = Depends(get_user)):
    r = sb.table("clients").insert({
        "user_id": user["id"],
        **payload.model_dump()
    }).select("*").execute()
    return r.data[0]
