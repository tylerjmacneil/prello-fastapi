# app/stripe_webhook.py
import os, stripe
from fastapi import APIRouter, Request, HTTPException
from .deps import sb

router = APIRouter(prefix="/stripe", tags=["stripe"])

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

@router.post("/webhook")
async def webhook(req: Request):
    payload = await req.body()
    sig = req.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    if event["type"] == "checkout.session.completed":
        sid = event["data"]["object"]["id"]
        job = sb.table("jobs").select("id").eq("checkout_session_id", sid).single().execute().data
        if job:
            sb.table("jobs").update({"status": "completed_paid"}).eq("id", job["id"]).execute()

    return {"ok": True}
