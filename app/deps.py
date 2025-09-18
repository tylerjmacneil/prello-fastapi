# app/deps.py
import os
from supabase import create_client, Client
from fastapi import Header, HTTPException
from typing import Dict, Any

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_user(authorization: str = Header(...)) -> Dict[str, Any]:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    u = sb.auth.get_user(token)
    if not u or not u.user:
        raise HTTPException(status_code=401, detail="Invalid token")

    auth_user_id = u.user.id
    row = sb.table("users").select("*").eq("auth_user_id", auth_user_id).single().execute()
    data = row.data
    if not data:
        email = u.user.email or ""
        created = sb.table("users").insert({"auth_user_id": auth_user_id, "email": email}).execute()
        data = created.data[0]
    return data  # contains public.users.id
