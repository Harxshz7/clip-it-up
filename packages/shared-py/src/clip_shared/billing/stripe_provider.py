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


class StripeBillingProvider(BillingProvider):
    """Stripe billing integration enabled behind PROVIDER_STRIPE_ENABLED flag for USD subscriptions."""

    def __init__(
        self,
        publishable_key: str | None = None,
        secret_key: str | None = None,
        webhook_secret: str | None = None,
    ):
        self.publishable_key = publishable_key or settings.STRIPE_PUBLISHABLE_KEY or "pk_test_mock"
        self.secret_key = secret_key or settings.STRIPE_SECRET_KEY or "sk_test_mock"
        self.webhook_secret = webhook_secret or settings.STRIPE_WEBHOOK_SECRET or "whsec_stripe_mock"

    @property
    def name(self) -> str:
        return "stripe"

    def create_customer(self, user_id: str, email: str, name: str) -> str:
        clean_user_id = user_id.replace("-", "")[:14]
        return f"cus_stripe_{clean_user_id}"

    def create_checkout(
        self,
        user_id: str,
        customer_id: str,
        plan_key: str,
        currency: str = "USD",
        return_url: str | None = None,
    ) -> CheckoutSessionResult:
        plans_cfg = load_plans_config().get("plans", {})
        plan_info = plans_cfg.get(plan_key, {})
        price_usd = Decimal(str(plan_info.get("price_usd_monthly", 19)))
        session_id = f"cs_test_{uuid.uuid4().hex[:14]}"

        base_app_url = settings.APP_BASE_URL.rstrip("/")
        ret_url = return_url or f"{base_app_url}/settings/billing?status=success&session_id={session_id}"
        hosted_url = f"https://checkout.stripe.com/c/pay/{session_id}"

        return CheckoutSessionResult(
            checkout_url=hosted_url,
            session_id=session_id,
            provider="stripe",
            currency="USD",
            amount=price_usd,
            plan_key=plan_key,
            metadata={"user_id": user_id, "customer_id": customer_id, "plan_key": plan_key},
        )

    def create_top_up_checkout(
        self,
        user_id: str,
        customer_id: str,
        pack_key: str,
        amount: Decimal,
        currency: str = "USD",
        return_url: str | None = None,
    ) -> CheckoutSessionResult:
        session_id = f"cs_test_topup_{uuid.uuid4().hex[:14]}"
        hosted_url = f"https://checkout.stripe.com/c/pay/{session_id}"
        return CheckoutSessionResult(
            checkout_url=hosted_url,
            session_id=session_id,
            provider="stripe",
            currency="USD",
            amount=amount,
            plan_key=pack_key,
            metadata={"user_id": user_id, "customer_id": customer_id, "pack_key": pack_key},
        )

    def cancel_subscription(self, provider_sub_id: str, at_period_end: bool = True) -> SubscriptionResult:
        now = datetime.now(UTC)
        return SubscriptionResult(
            subscription_id=provider_sub_id,
            customer_id="",
            plan_key="",
            status="canceled",
            currency="USD",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=at_period_end,
        )

    def resume_subscription(self, provider_sub_id: str) -> SubscriptionResult:
        now = datetime.now(UTC)
        return SubscriptionResult(
            subscription_id=provider_sub_id,
            customer_id="",
            plan_key="",
            status="active",
            currency="USD",
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
            currency="USD",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
            metadata={"prorated": prorate},
        )

    def get_portal_url(self, customer_id: str, return_url: str) -> str:
        return f"https://billing.stripe.com/p/session_{customer_id}"

    def verify_webhook_signature(self, raw_payload: bytes, signature_header: str) -> bool:
        if not signature_header:
            return False
        # Stripe signature header format: t=1492774577,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
        parts = dict(item.strip().split("=", 1) for item in signature_header.split(",") if "=" in item)
        timestamp = parts.get("t")
        v1_sig = parts.get("v1")
        if not timestamp or not v1_sig:
            return False

        signed_payload = f"{timestamp}.".encode("utf-8") + raw_payload
        expected_sig = hmac.new(self.webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, v1_sig)

    def parse_webhook_event(self, raw_payload: bytes, headers: dict[str, str]) -> WebhookParsedEvent:
        sig = headers.get("stripe-signature") or headers.get("Stripe-Signature") or ""
        if not self.verify_webhook_signature(raw_payload, sig):
            raise WebhookVerificationError("Stripe signature verification failed")

        data = json.loads(raw_payload.decode("utf-8"))
        event_name = data.get("type", "unknown")
        event_id = data.get("id", f"evt_stripe_{uuid.uuid4().hex[:12]}")
        obj = data.get("data", {}).get("object", {})

        sub_id = obj.get("id") if event_name.startswith("customer.subscription") else obj.get("subscription")
        cust_id = obj.get("customer")
        status_map = {
            "active": "active",
            "trialing": "active",
            "past_due": "past_due",
            "canceled": "canceled",
            "unpaid": "expired",
            "incomplete_expired": "expired",
        }
        internal_status = status_map.get(obj.get("status", ""), "active")
        if event_name == "invoice.payment_failed":
            internal_status = "past_due"

        now = datetime.now(UTC)
        cur_start_ts = obj.get("current_period_start")
        cur_end_ts = obj.get("current_period_end")
        period_start = datetime.fromtimestamp(cur_start_ts, tz=UTC) if cur_start_ts else now
        period_end = datetime.fromtimestamp(cur_end_ts, tz=UTC) if cur_end_ts else now + timedelta(days=30)

        raw_amt = obj.get("amount_paid") or obj.get("amount") or 0
        amount = Decimal(str(raw_amt)) / Decimal("100")
        currency = (obj.get("currency") or "USD").upper()

        return WebhookParsedEvent(
            event_id=event_id,
            event_type=event_name,
            provider="stripe",
            resource_id=sub_id or event_id,
            status=internal_status,
            payload=data,
            current_period_start=period_start,
            current_period_end=period_end,
            amount=amount,
            currency=currency,
            customer_id=cust_id,
            plan_key="creator",
            payment_id=obj.get("payment_intent") or obj.get("charge"),
            error_message=obj.get("failure_message"),
        )
