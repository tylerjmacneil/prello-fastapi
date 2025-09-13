# app/auth.py
import os
import time
import requests
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

# ---- Config (from Railway env vars) ----
PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")  # e.g. lrxyfyzgrkvnoezjfycv
ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

if not PROJECT_REF:
    raise RuntimeError("SUPABASE_PROJECT_REF not set")

JWKS_URL = f"https://{PROJECT_REF}.supabase.co/auth/v1/keys"
ISSUER = f"https://{PROJECT_REF}.supabase.co/auth/v1"
AUDIENCE = "authenticated"  # Supabase default audience

security = HTTPBearer()
_cache = {"jwks": None, "fetched_at": 0}

def _get_jwks():
    """Fetch Supabase JWKS; include anon key headers if the project requires it."""
    now = time.time()
    if not _cache["jwks"] or now - _cache["fetched_at"] > 600:
        headers = {}
        if ANON_KEY:
            headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}
        resp = requests.get(JWKS_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        _cache["jwks"] = resp.json()
        _cache["fetched_at"] = now
    return _cache["jwks"]

def verify_and_get_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verify a Supabase JWT (Authorization: Bearer <token>) and return the user's UUID (sub).
    """
    token = credentials.credentials
    jwks = _get_jwks()

    # Pick the matching key by 'kid'
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
    if not key:
        raise HTTPException(status_code=401, detail="Signing key not found")

    try:
        # jose accepts a single JWK dict as the key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={
                "verify_aud": False,     # some setups omit aud; disable to be forgiving
                "verify_at_hash": False,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject (sub)")
    return sub

