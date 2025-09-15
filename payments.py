# payments.py
import os, stripe
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/payments", tags=["payments"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

@router.get("/ping")
async def ping():
    return {"ok": True}

@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=sig_header, secret=WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Temporary log handling
    if event["type"] == "checkout.session.completed":
        print("✅ Checkout session completed")
    elif event["type"] == "payment_intent.succeeded":
        print("✅ Payment succeeded")

    return {"ok": True}
