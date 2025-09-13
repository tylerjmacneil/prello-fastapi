# app/auth.py
import os
import time
import requests
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")  # e.g. lrxyfyzgrkvnoezjfycv
ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")  # <- HS256 secret

if not PROJECT_REF:
    raise RuntimeError("SUPABASE_PROJECT_REF not set")

JWKS_URL = f"https://{PROJECT_REF}.supabase.co/auth/v1/.well-known/jwks.json"
ISSUER = f"https://{PROJECT_REF}.supabase.co/auth/v1"

security = HTTPBearer()
_cache = {"jwks": None, "fetched_at": 0}


def _get_jwks():
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


def _fetch_user_id_from_supabase(token: str) -> str:
    """Fallback: ask Supabase who this token belongs to."""
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": ANON_KEY or "",
    }
    url = f"https://{PROJECT_REF}.supabase.co/auth/v1/user"
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Could not verify token with Supabase")
    data = r.json() or {}
    uid = data.get("id") or (data.get("user") or {}).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="User id not found from Supabase")
    return uid


def verify_and_get_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Accepts Supabase access tokens signed with:
      - HS256 (JWT secret)  -> verify with SUPABASE_JWT_SECRET
      - RS256 (JWKS)        -> verify with JWKS
    Falls back to /auth/v1/user if needed.
    """
    token = credentials.credentials

    # Determine algorithm without verifying signature
    try:
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg", "")
    except Exception:
        # If header can't be parsed, try fallback to Supabase
        return _fetch_user_id_from_supabase(token)

    # HS256 path (most Supabase projects)
    if alg.upper() == "HS256":
        if not JWT_SECRET:
            # No secret available — fallback to Supabase
            return _fetch_user_id_from_supabase(token)
        try:
            claims = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
                issuer=ISSUER,
            )
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token (HS256): {e}")
        sub = claims.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Token missing subject (sub)")
        return sub

    # RS256 path (rare in Supabase)
    if alg.upper() == "RS256":
        jwks = _get_jwks()
        kid = unverified_header.get("kid")
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not key:
            raise HTTPException(status_code=401, detail="Signing key not found")
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                options={"verify_aud": False},
                issuer=ISSUER,
            )
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token (RS256): {e}")
        sub = claims.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Token missing subject (sub)")
        return sub

    # Unknown/other alg — fallback
    return _fetch_user_id_from_supabase(token)

