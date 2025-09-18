# app/main.py
from fastapi import FastAPI
from .clients import router as clients_router
from .jobs import router as jobs_router
from .payments import router as payments_router
from .stripe_webhook import router as stripe_router

app = FastAPI(title="Prello API", version="1.0.0")

@app.get("/health")
def health(): return {"ok": True}

@app.get("/")
def root(): return {"name": "prello-api"}

# routers
app.include_router(clients_router)
app.include_router(jobs_router)
app.include_router(payments_router)
app.include_router(stripe_router)
