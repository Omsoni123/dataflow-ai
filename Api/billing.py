import os
import hmac
import hashlib

import razorpay
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from Api.auth import get_current_user
from SRC.database import get_connection


router = APIRouter(
    prefix="/billing",
    tags=["Billing"],
)


# ============================================================
# Razorpay Configuration
# ============================================================

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_PLAN_ID = os.getenv("RAZORPAY_PLAN_ID")


if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    raise ValueError("Razorpay API credentials are not configured.")


if not RAZORPAY_PLAN_ID:
    raise ValueError("RAZORPAY_PLAN_ID is not configured.")


razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)


# ============================================================
# Request Models
# ============================================================

class VerifySubscriptionRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_subscription_id: str
    razorpay_signature: str


# ============================================================
# Create Razorpay Subscription
# ============================================================

@router.post("/create-subscription")
def create_subscription(
    current_user: dict = Depends(get_current_user),
):
    """
    Create a Razorpay recurring subscription
    for the authenticated DataFlow AI user.
    """

    user_id = current_user["user_id"]

    try:
        subscription = razorpay_client.subscription.create(
            {
                "plan_id": RAZORPAY_PLAN_ID,
                "total_count": 12,
                "customer_notify": 1,
            }
        )

        subscription_id = subscription["id"]

        with get_connection() as connection:
            connection.execute(
                text("""
                    UPDATE users
                    SET razorpay_subscription_id = :subscription_id,
                        subscription_status = 'created'
                    WHERE user_id = :user_id
                """),
                {
                    "subscription_id": subscription_id,
                    "user_id": user_id,
                },
            )

            connection.commit()

        return {
            "success": True,
            "subscription_id": subscription_id,
            "razorpay_key_id": RAZORPAY_KEY_ID,
            "plan_id": RAZORPAY_PLAN_ID,
            "amount": 49900,
            "currency": "INR",
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to create subscription: {str(error)}",
        )


# ============================================================
# Verify Razorpay Subscription Payment
# ============================================================

@router.post("/verify-subscription")
def verify_subscription(
    data: VerifySubscriptionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Verify Razorpay subscription payment signature.

    Only after successful verification is the user's
    DataFlow AI plan upgraded to Pro.
    """

    user_id = current_user["user_id"]

    try:
        # ----------------------------------------------------
        # 1. Get the subscription stored for this user
        # ----------------------------------------------------

        with get_connection() as connection:
            result = connection.execute(
                text("""
                    SELECT
                        razorpay_subscription_id,
                        plan,
                        subscription_status
                    FROM users
                    WHERE user_id = :user_id
                """),
                {
                    "user_id": user_id,
                },
            ).fetchone()

        if not result:
            raise HTTPException(
                status_code=404,
                detail="User account not found.",
            )

        stored_subscription_id = result[0]
        current_plan = result[1]
        current_subscription_status = result[2]

        # ----------------------------------------------------
        # 2. Make sure Razorpay subscription belongs to user
        # ----------------------------------------------------

        if not stored_subscription_id:
            raise HTTPException(
                status_code=400,
                detail="No Razorpay subscription found for this user.",
            )

        if stored_subscription_id != data.razorpay_subscription_id:
            raise HTTPException(
                status_code=403,
                detail="Subscription does not belong to this user.",
            )

        # ----------------------------------------------------
        # 3. Prevent unnecessary duplicate activation
        # ----------------------------------------------------

        if (
            current_plan == "pro"
            and current_subscription_status == "active"
        ):
            return {
                "success": True,
                "message": "Subscription is already active.",
                "plan": "pro",
                "subscription_status": "active",
            }

        # ----------------------------------------------------
        # 4. Create expected Razorpay signature
        #
        # Razorpay subscription signature:
        #
        # razorpay_payment_id
        # +
        # "|"
        # +
        # razorpay_subscription_id
        # ----------------------------------------------------

        signature_payload = (
            data.razorpay_payment_id
            + "|"
            + data.razorpay_subscription_id
        )

        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode("utf-8"),
            signature_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # ----------------------------------------------------
        # 5. Secure comparison
        # ----------------------------------------------------

        if not hmac.compare_digest(
            generated_signature,
            data.razorpay_signature,
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid Razorpay payment signature.",
            )

        # ----------------------------------------------------
        # 6. Signature verified → activate Pro
        # ----------------------------------------------------

        with get_connection() as connection:
            connection.execute(
                text("""
                    UPDATE users
                    SET plan = 'pro',
                        subscription_status = 'active'
                    WHERE user_id = :user_id
                """),
                {
                    "user_id": user_id,
                },
            )

            connection.commit()

        # ----------------------------------------------------
        # 7. Return successful activation
        # ----------------------------------------------------

        return {
            "success": True,
            "message": "Subscription verified successfully.",
            "plan": "pro",
            "subscription_status": "active",
            "subscription_id": data.razorpay_subscription_id,
            "payment_id": data.razorpay_payment_id,
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Subscription verification failed: {str(error)}",
        )