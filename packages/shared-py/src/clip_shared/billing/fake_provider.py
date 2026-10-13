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


class FakeBillingProvider(BillingProvider):
    """Deterministic in-memory billing provider for offline automated test suites."""

    def __init__(self, webhook_secret: str = "fake_test_webhook_secret"):
        self.webhook_secret = webhook_secret
        self.customers: dict[str, str] = {}  # user_id -> customer_id
        self.subscriptions: dict[str, dict[str, Any]] = {}
        self.checkout_sessions: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "fake"

    def create_customer(self, user_id: str, email: str, name: str) -> str:
        if user_id not in self.customers:
            self.customers[user_id] = f"cust_fake_{uuid.uuid4().hex[:8]}"
        return self.customers[user_id]

    def create_checkout(
        self,
        user_id: str,
        customer_id: str,
        plan_key: str,
        currency: str = "INR",
        return_url: str | None = None,
    ) -> CheckoutSessionResult:
        sub_id = f"sub_fake_{uuid.uuid4().hex[:8]}"
        now = datetime.now(UTC)
        self.subscriptions[sub_id] = {
            "user_id": user_id,
            "customer_id": customer_id,
            "plan_key": plan_key,
            "status": "pending",
            "currency": currency,
            "period_start": now,
            "period_end": now + timedelta(days=30),
        }
        return CheckoutSessionResult(
            checkout_url=f"http://localhost:3000/fake-checkout?sub_id={sub_id}",
            session_id=sub_id,
            provider="fake",
            currency=currency,
            amount=Decimal("1499.00") if plan_key == "creator" else Decimal("3999.00"),
            plan_key=plan_key,
            metadata={"user_id": user_id, "customer_id": customer_id},
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
        order_id = f"order_fake_{uuid.uuid4().hex[:8]}"
        return CheckoutSessionResult(
            checkout_url=f"http://localhost:3000/fake-checkout?order_id={order_id}",
            session_id=order_id,
            provider="fake",
            currency=currency,
            amount=amount,
            plan_key=pack_key,
            metadata={"user_id": user_id, "customer_id": customer_id, "pack_key": pack_key},
        )

    def cancel_subscription(self, provider_sub_id: str, at_period_end: bool = True) -> SubscriptionResult:
        now = datetime.now(UTC)
        sub = self.subscriptions.get(provider_sub_id, {})
        sub["status"] = "canceled"
        return SubscriptionResult(
            subscription_id=provider_sub_id,
            customer_id=sub.get("customer_id", ""),
            plan_key=sub.get("plan_key", "creator"),
            status="canceled",
            currency=sub.get("currency", "INR"),
            current_period_start=sub.get("period_start", now),
            current_period_end=sub.get("period_end", now + timedelta(days=30)),
            cancel_at_period_end=at_period_end,
        )

    def resume_subscription(self, provider_sub_id: str) -> SubscriptionResult:
        now = datetime.now(UTC)
        sub = self.subscriptions.get(provider_sub_id, {})
        sub["status"] = "active"
        return SubscriptionResult(
            subscription_id=provider_sub_id,
            customer_id=sub.get("customer_id", ""),
            plan_key=sub.get("plan_key", "creator"),
            status="active",
            currency=sub.get("currency", "INR"),
            current_period_start=sub.get("period_start", now),
            current_period_end=sub.get("period_end", now + timedelta(days=30)),
            cancel_at_period_end=False,
        )

    def change_plan(self, provider_sub_id: str, new_plan_key: str, prorate: bool = True) -> SubscriptionResult:
        now = datetime.now(UTC)
        sub = self.subscriptions.get(provider_sub_id, {})
        sub["plan_key"] = new_plan_key
        return SubscriptionResult(
            subscription_id=provider_sub_id,
            customer_id=sub.get("customer_id", ""),
            plan_key=new_plan_key,
            status="active",
            currency=sub.get("currency", "INR"),
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
            metadata={"prorated": prorate},
        )

    def get_portal_url(self, customer_id: str, return_url: str) -> str:
        return f"http://localhost:3000/settings/billing?customer={customer_id}"

    def sign_payload(self, raw_payload: bytes) -> str:
        """Utility for test suites to generate a valid test webhook signature."""
        return hmac.new(self.webhook_secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()

    def verify_webhook_signature(self, raw_payload: bytes, signature_header: str) -> bool:
        expected = self.sign_payload(raw_payload)
        return hmac.compare_digest(expected, signature_header.strip())

    def parse_webhook_event(self, raw_payload: bytes, headers: dict[str, str]) -> WebhookParsedEvent:
        sig = headers.get("x-signature") or headers.get("x-razorpay-signature") or headers.get("stripe-signature") or ""
        if not self.verify_webhook_signature(raw_payload, sig):
            raise WebhookVerificationError("Fake provider signature verification failed")

        data = json.loads(raw_payload.decode("utf-8"))
        now = datetime.now(UTC)
        return WebhookParsedEvent(
            event_id=data.get("id", f"evt_fake_{uuid.uuid4().hex[:8]}"),
            event_type=data.get("event", "subscription.charged"),
            provider="fake",
            resource_id=data.get("resource_id", "sub_fake_default"),
            status=data.get("status", "active"),
            payload=data,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            amount=Decimal(str(data.get("amount", "1499.00"))),
            currency=data.get("currency", "INR"),
            customer_id=data.get("customer_id", "cust_fake_default"),
            plan_key=data.get("plan_key", "creator"),
            payment_id=data.get("payment_id", f"pay_fake_{uuid.uuid4().hex[:8]}"),
            error_message=data.get("error_message"),
        )
