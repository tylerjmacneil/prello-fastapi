# app/payments.py
import os, stripe
from fastapi import APIRouter, Depends, HTTPException
from .deps import sb, get_user
from .models import CheckoutOut

router = APIRouter(prefix="/jobs", tags=["payments"])
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

CURRENCY = os.environ.get("STRIPE_CURRENCY", "usd")
SUCCESS_URL = os.environ.get("SUCCESS_URL", "https://prello.app/success")
CANCEL_URL  = os.environ.get("CANCEL_URL",  "https://prello.app/cancel")

@router.post("/{job_id}/checkout", response_model=CheckoutOut)
async def create_checkout(job_id: str, user = Depends(get_user)):
    job = sb.table("jobs").select("*").eq("id", job_id).single().execute().data
    if not job or job["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Job not found")

    sess = stripe.checkout.Session.create(
        mode="payment",
        currency=CURRENCY,
        line_items=[{
            "price_data": {
                "currency": CURRENCY,
                "product_data": {"name": job["title"]},
                "unit_amount": job["price_cents"],
            },
            "quantity": 1,
        }],
        success_url=SUCCESS_URL,
        cancel_url=CANCEL_URL,
        automatic_payment_methods={"enabled": True}  # BNPL shows when enabled in Stripe dashboard
    )

    sb.table("jobs").update({"checkout_session_id": sess.id}).eq("id", job_id).execute()
    return {"checkout_url": sess.url}
