# app/models.py
from pydantic import BaseModel, Field
from typing import Optional

class ClientIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class JobIn(BaseModel):
    client_id: str
    title: str
    description: Optional[str] = None
    price_cents: int = Field(ge=0)
    status: str = "active_unscheduled"

class CheckoutOut(BaseModel):
    checkout_url: str
