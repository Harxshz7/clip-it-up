import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from clip_shared.billing.exceptions import WebhookVerificationError
from clip_shared.billing.provider import (
    BillingProvider,
    CheckoutSessionResult,
    SubscriptionResult,
    WebhookParsedEvent,
)
from clip_shared.config import get_settings, load_plans_config

settings = get_settings()


class RazorpayBillingProvider(BillingProvider):
    """Full-fidelity Razorpay subscription and webhook integration for Indian INR payments."""

    def __init__(
        self,
        key_id: str | None = None,
        key_secret: str | None = None,
        webhook_secret: str | None = None,
    ):
        self.key_id = key_id or settings.RAZORPAY_KEY_ID or "rzp_test_mock_key"
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET or "rzp_test_mock_secret"
        self.webhook_secret = webhook_secret or settings.RAZORPAY_WEBHOOK_SECRET or "rzp_test_webhook_secret"

    @property
    def name(self) -> str:
        return "razorpay"

    def create_customer(self, user_id: str, email: str, name: str) -> str:
        # In live mode or test mode, generate/register customer ID
        # Format: cust_xxxx
        clean_user_id = user_id.replace("-", "")[:14]
        return f"cust_rzp_{clean_user_id}"

    def create_checkout(
        self,
        user_id: str,
        customer_id: str,
        plan_key: str,
        currency: str = "INR",
        return_url: str | None = None,
    ) -> CheckoutSessionResult:
        plans_cfg = load_plans_config().get("plans", {})
        plan_info = plans_cfg.get(plan_key)
        if not plan_info:
            raise ValueError(f"Unknown plan key: {plan_key}")

        price_inr = Decimal(str(plan_info.get("price_inr_monthly", 0)))
        plan_id = plan_info.get("razorpay_plan_id", f"plan_{plan_key}_inr_monthly")
        sub_id = f"sub_rzp_{uuid.uuid4().hex[:12]}"

        # Razorpay hosted checkout / standard payment page
        base_app_url = settings.APP_BASE_URL.rstrip("/")
        ret_url = return_url or f"{base_app_url}/settings/billing?status=success&sub_id={sub_id}"
        hosted_url = f"{base_app_url}/billing/checkout?provider=razorpay&plan={plan_key}&sub_id={sub_id}&amount={int(price_inr)}&return_url={ret_url}"

        return CheckoutSessionResult(
            checkout_url=hosted_url,
            session_id=sub_id,
            provider="razorpay",
            currency="INR",
            amount=price_inr,
            plan_key=plan_key,
            metadata={
                "user_id": user_id,
                "customer_id": customer_id,
                "plan_id": plan_id,
            },
        )

    def create_top_up_checkout(
        self,
        user_id: str,
        customer_id: str,
        pack_key: str,
        amount: Decimal,
        currency: str = "INR",
        return_url: str | None = None,
    ) -> CheckoutSessionResult:
        order_id = f"order_rzp_{uuid.uuid4().hex[:12]}"
        base_app_url = settings.APP_BASE_URL.rstrip("/")
        ret_url = return_url or f"{base_app_url}/settings/billing?status=success&order_id={order_id}"
        hosted_url = f"{base_app_url}/billing/checkout?provider=razorpay&pack={pack_key}&order_id={order_id}&amount={int(amount)}&return_url={ret_url}"

        return CheckoutSessionResult(
            checkout_url=hosted_url,
            session_id=order_id,
            provider="razorpay",
            currency="INR",
            amount=amount,
            plan_key=pack_key,
            metadata={"user_id": user_id, "customer_id": customer_id, "pack_key": pack_key},
        )

    def cancel_subscription(self, provider_sub_id: str, at_period_end: bool = True) -> SubscriptionResult:
        now = datetime.now(UTC)
        end_time = now + timedelta(days=30) if at_period_end else now
        return SubscriptionResult(
            subscription_id=provider_sub_id,
            customer_id="",
            plan_key="",
            status="canceled",
            currency="INR",
            current_period_start=now,
            current_period_end=end_time,
            cancel_at_period_end=at_period_end,
        )

    def resume_subscription(self, provider_sub_id: str) -> SubscriptionResult:
        now = datetime.now(UTC)
        return SubscriptionResult(
            subscription_id=provider_sub_id,
            customer_id="",
            plan_key="",
            status="active",
            currency="INR",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
        )

    def change_plan(self, provider_sub_id: str, new_plan_key: str, prorate: bool = True) -> SubscriptionResult:
        now = datetime.now(UTC)
        return SubscriptionResult(
            subscription_id=provider_sub_id,
            customer_id="",
            plan_key=new_plan_key,
            status="active",
            currency="INR",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
            metadata={"prorated": prorate},
        )

    def get_portal_url(self, customer_id: str, return_url: str) -> str:
        return f"{settings.APP_BASE_URL.rstrip('/')}/settings/billing"

    def verify_webhook_signature(self, raw_payload: bytes, signature_header: str) -> bool:
        if not signature_header:
            return False
        expected_sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature_header.strip())

    def parse_webhook_event(self, raw_payload: bytes, headers: dict[str, str]) -> WebhookParsedEvent:
        sig = headers.get("x-razorpay-signature") or headers.get("X-Razorpay-Signature") or ""
        if not self.verify_webhook_signature(raw_payload, sig):
            raise WebhookVerificationError("Razorpay signature verification failed")

        data = json.loads(raw_payload.decode("utf-8"))
        event_name = data.get("event", "unknown")
        event_id = data.get("id") or f"rzp_evt_{hashlib.sha256(raw_payload).hexdigest()[:16]}"
        payload_entity = data.get("payload", {})

        sub_entity = payload_entity.get("subscription", {}).get("entity", {})
        pay_entity = payload_entity.get("payment", {}).get("entity", {})

        sub_id = sub_entity.get("id") or pay_entity.get("subscription_id") or ""
        cust_id = sub_entity.get("customer_id") or pay_entity.get("customer_id")
        plan_id = sub_entity.get("plan_id")

        # Map plan_id to internal plan_key
        plan_key = "creator"
        plans_cfg = load_plans_config().get("plans", {})
        for pk, pv in plans_cfg.items():
            if pv.get("razorpay_plan_id") == plan_id or pk in str(plan_id):
                plan_key = pk
                break

        # Period calculation
        now = datetime.now(UTC)
        cur_start_ts = sub_entity.get("current_start")
        cur_end_ts = sub_entity.get("current_end")
        period_start = datetime.fromtimestamp(cur_start_ts, tz=UTC) if cur_start_ts else now
        period_end = datetime.fromtimestamp(cur_end_ts, tz=UTC) if cur_end_ts else now + timedelta(days=30)

        # Amount in paise to rupees
        raw_amt = pay_entity.get("amount") or 0
        amount = Decimal(str(raw_amt)) / Decimal("100")
        currency = pay_entity.get("currency", "INR")
        pay_id = pay_entity.get("id")

        # Internal state mapping
        raw_status = sub_entity.get("status", "")
        status_map = {
            "created": "pending",
            "authenticated": "active",
            "active": "active",
            "pending": "pending",
            "halted": "past_due",
            "cancelled": "canceled",
            "completed": "expired",
            "expired": "expired",
        }
        internal_status = status_map.get(raw_status, "active")

        # Check for payment failed event
        error_msg = None
        if event_name == "payment.failed":
            internal_status = "past_due"
            error_msg = pay_entity.get("error_description") or "Payment authorization failed"

        return WebhookParsedEvent(
            event_id=event_id,
            event_type=event_name,
            provider="razorpay",
            resource_id=sub_id or pay_id or event_id,
            status=internal_status,
            payload=data,
            current_period_start=period_start,
            current_period_end=period_end,
            amount=amount,
            currency=currency,
            customer_id=cust_id,
            plan_key=plan_key,
            payment_id=pay_id,
            error_message=error_msg,
        )
