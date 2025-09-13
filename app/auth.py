# app/auth.py
import os
import time
import requests
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from jose.exceptions import JWTError

# Config from Railway env vars
SUPABASE_PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_PROJECT_REF:
    raise RuntimeError("Missing SUPABASE_PROJECT_REF environment variable")

JWKS_URL = f"https://{SUPABASE_PROJECT_REF}.supabase.co/auth/v1/keys"

security = HTTPBearer()

_cache = {"jwks": None, "fetched_at": 0}


def _get_jwks():
    """Fetch JWKS (public keys) from Supabase, with anon key if required."""
    now = time.time()
    if not _cache["jwks"] or now - _cache["fetched_at"] > 600:
        headers = {}
        if SUPABASE_ANON_KEY:
            headers = {
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
            }
        resp = requests.get(JWKS_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        _cache["jwks"] = resp.json()
        _cache["fetched_at"] = now
    return _cache["jwks"]


def verify_and_get_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_user_id: str = Header(None)
):
    """Verify JWT, return user_id from token (or header override)."""
    token = credentials.credentials
    jwks = _get_jwks()

    try:
        # jose can validate against the JWKS set
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False}  # Supabase tokens don’t always set aud
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")

    # Optional: allow overriding via X-User-Id (useful for Swagger testing)
    return x_user_id or user_id

