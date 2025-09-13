from fastapi import FastAPI
from app.routers import health, clients

app = FastAPI()

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(clients.router, prefix="/clients", tags=["clients"])

@app.get("/")
def read_root():
    return {"hello": "prello"}

