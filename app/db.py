import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

_engine = None
_SessionLocal = None

def _ensure_engine():
    global _engine, _SessionLocal
    if _engine is None:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            # defer failure until a DB-using endpoint is called
            raise RuntimeError("SUPABASE_DB_URL is not set")
        _engine = create_async_engine(db_url, echo=False, pool_size=5, max_overflow=10)
        _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

async def get_session() -> AsyncSession:
    _ensure_engine()
    async with _SessionLocal() as session:
        yield session

