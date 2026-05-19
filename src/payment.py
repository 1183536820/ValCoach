import os
import stripe
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")

stripe.api_key = STRIPE_SECRET_KEY


def create_checkout_session(user_id: int, success_url: str, cancel_url: str) -> Optional[str]:
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": STRIPE_PRICE_ID,
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={"user_id": str(user_id)},
        )
        return checkout_session.url
    except Exception as e:
        raise RuntimeError(f"Failed to create checkout session: {str(e)}")


def verify_payment(session_id: str) -> Optional[dict]:
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            return {
                "user_id": int(session.metadata.get("user_id", 0)),
                "amount": session.amount_total / 100 if session.amount_total else 9.9,
            }
        return None
    except Exception:
        return None
