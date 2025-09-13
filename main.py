from fastapi import FastAPI
from app.routers import health, clients

app = FastAPI(title="Prello API", version="0.1.0")

@app.get("/")
def read_root():
    return {"hello": "prello"}

# Mount routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(clients.router, prefix="/clients", tags=["clients"])

