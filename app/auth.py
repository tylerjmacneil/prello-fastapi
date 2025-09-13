import os, time, requests
from typing import Optional, Dict, Any
from jose import jwt

# e.g. lrxyfyzgrkvnoezjfycv  (the random project id in your Supabase URL)
PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")
if not PROJECT_REF:
    raise RuntimeError("SUPABASE_PROJECT_REF not set")

JWKS_URL = f"https://{PROJECT_REF}.supabase.co/auth/v1/keys"
ISSUER = f"https://{PROJECT_REF}.supabase.co/auth/v1"
AUDIENCE = "authenticated"

_cache: Dict[str, Any] = {"jwks": None, "fetched_at": 0}

def _get_jwks():
    now = time.time()
    if not _cache["jwks"] or now - _cache["fetched_at"] > 600:
        resp = requests.get(JWKS_URL, timeout=10)
        resp.raise_for_status()
        _cache["jwks"] = resp.json()
        _cache["fetched_at"] = now
    return _cache["jwks"]

def verify_and_get_user_id(bearer: Optional[str]) -> str:
    """
    Expect Authorization: Bearer <token>; returns the Supabase user id (sub).
    """
    if not bearer or not bearer.lower().startswith("bearer "):
        raise ValueError("Missing or invalid Authorization header")
    token = bearer.split(" ", 1)[1]

    unverified = jwt.get_unverified_header(token)
    jwks = _get_jwks()
    key = next((k for k in jwks["keys"] if k.get("kid") == unverified.get("kid")), None)
    if not key:
        raise ValueError("Signing key not found")

    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=AUDIENCE,
        issuer=ISSUER,
        options={"verify_at_hash": False},
    )
    return claims["sub"]

