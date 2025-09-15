# payments.py
import os
import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
import stripe

from auth import get_current_user  # verifies Supabase JWT via /auth/v1/user

router = APIRouter(prefix="/payments", tags=["payments"])

# Stripe config from env
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

logger = logging.getLogger("uvicorn")

# ---- Health / sanity check ---------------------------------------------------
@router.get("/ping")
async def ping():
    return {
        "ok": True,
        "has_secret_key": bool(stripe.api_key),
        "has_webhook_secret": bool(WEBHOOK_SECRET),
    }

# ---- Webhook (no auth) -------------------------------------------------------
@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not WEBHOOK_SECRET:
        logger.error("Stripe webhook secret missing (STRIPE_WEBHOOK_SECRET)")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Verify signature
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=WEBHOOK_SECRET
        )
    except Exception as e:
        masked = WEBHOOK_SECRET[:6] + "..." + WEBHOOK_SECRET[-4:] if WEBHOOK_SECRET else "MISSING"
        logger.error(
            f"Stripe webhook verify FAILED: {e}; "
            f"sig_header_present={bool(sig_header)}; "
            f"secret={masked}"
        )
        raise HTTPException(status_code=400, detail="signature verification failed")

    # Minimal handlers to prove flow
    etype = event.get("type")
    logger.info(f"Stripe webhook received: {etype}")

    if etype == "checkout.session.completed":
        sess = event["data"]["object"]
        logger.info(f"✅ checkout.session.completed for session {sess.get('id')}")
        # TODO: write to Supabase (payments table), update job status, etc.
    elif etype == "payment_intent.succeeded":
        intent = event["data"]["object"]
        logger.info(f"✅ payment_intent.succeeded for intent {intent.get('id')}")
        # TODO: same as above if you prefer to key off PI events

    return {"ok": True}

# ---- Create Checkout Session (auth required) --------------------------------
class CheckoutPayload(BaseModel):
    job_id: str
    amount_cents: int
    currency: str = "cad"
    customer_email: str
    success_url: str  # e.g., prello://payment-success?job_id=...
    cancel_url: str   # e.g., prello://payment-cancel?job_id=...

@router.post("/checkout")
async def create_checkout_session(
    body: CheckoutPayload,
    user=Depends(get_current_user)  # 🔒 require valid Supabase JWT
):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe secret key missing")

    contractor_id = user.get("id")  # Supabase user id

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
            metadata={
                "job_id": body.job_id,
                "contractor_id": contractor_id
            }
        )
    except Exception as e:
        logger.error(f"Stripe Checkout create failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to create checkout session")

    logger.info(f"Created checkout session {session.get('id')} for job {body.job_id} by user {contractor_id}")
    return {"checkout_url": session.get("url"), "session_id": session.get("id")}

