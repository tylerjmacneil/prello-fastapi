from fastapi import FastAPI
from app.routers import health, clients

app = FastAPI()

# Root
@app.get("/")
def read_root():
    return {"hello": "prello"}

# Routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(clients.router, prefix="/clients", tags=["clients"])

