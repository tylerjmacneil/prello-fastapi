from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db import get_session

router = APIRouter()

@router.get("/db")
async def health_db(db: AsyncSession = Depends(get_session)):
    try:
        result = await db.execute(text("select 1"))
        return {"db": result.scalar_one()}
    except Exception as e:
        # surface the error so we know exactly what's wrong
        return {"error": str(e)}

