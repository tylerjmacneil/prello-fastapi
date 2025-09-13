from fastapi import FastAPI
from app.routers import health

app = FastAPI()

# add the health routes
app.include_router(health.router, prefix="/health", tags=["health"])

@app.get("/")
def read_root():
    return {"hello": "prello"}
