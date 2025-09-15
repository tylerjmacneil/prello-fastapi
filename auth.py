# auth.py
import os
import httpx
from fastapi import Header, HTTPException

SUPABASE_URL = os.environ["SUPABASE_URL"]

async def get_current_user(authorization: str = Header(...)):
    """Verify the Supabase user JWT sent from the iOS app."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1]

    # Ask Supabase to validate the token and return the user
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": token,  # Supabase accepts the user JWT as apikey here
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return resp.json()  # contains at least { "id": "<user-id>", ... }
