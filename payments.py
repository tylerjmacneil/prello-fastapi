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
    from pydantic import BaseModel

class CheckoutPayload(BaseModel):
    job_id: str
    amount_cents: int
    currency: str = "cad"
    customer_email: str
    success_url: str  # e.g., prello://payment-success?job_id=...
    cancel_url: str   # e.g., prello://payment-cancel?job_id=...

@router.post("/checkout")
async def create_checkout_session(body: CheckoutPayload):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe secret key missing")

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=body.customer_email,
            line_items=[{
                "price_data": {
                    "currency": body.currency,
                    "product_data": {"name": f"Job {body.job_id}"},
                    "unit_amount": body.amount_cents
                },
                "quantity": 1
            }],
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            metadata={"job_id": body.job_id}
        )
    except Exception as e:
        logger.error(f"Stripe Checkout create failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to create checkout session")

    logger.info(f"Created checkout session {session.get('id')} for job {body.job_id}")
    return {"checkout_url": session.get("url"), "session_id": session.get("id")}

