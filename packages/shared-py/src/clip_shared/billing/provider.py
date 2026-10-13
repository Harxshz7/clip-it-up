from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class CheckoutSessionResult:
    checkout_url: str
    session_id: str
    provider: str
    currency: str
    amount: Decimal
    plan_key: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubscriptionResult:
    subscription_id: str
    customer_id: str
    plan_key: str
    status: str  # active | past_due | canceled | expired | pending | halted
    currency: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookParsedEvent:
    event_id: str
    event_type: str
    provider: str
    resource_id: str
    status: str
    payload: dict[str, Any]
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    amount: Decimal | None = None
    currency: str = "INR"
    customer_id: str | None = None
    plan_key: str | None = None
    payment_id: str | None = None
    error_message: str | None = None


class BillingProvider(ABC):
    """Abstract interface defining required payment gateway operations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name: 'razorpay' | 'stripe' | 'fake'"""
        pass

    @abstractmethod
    def create_customer(self, user_id: str, email: str, name: str) -> str:
        """Create or fetch customer and return gateway customer_id."""
        pass

    @abstractmethod
    def create_checkout(
        self,
        user_id: str,
        customer_id: str,
        plan_key: str,
        currency: str = "INR",
        return_url: str | None = None,
    ) -> CheckoutSessionResult:
        """Create hosted subscription checkout session."""
        pass

    @abstractmethod
    def create_top_up_checkout(
        self,
        user_id: str,
        customer_id: str,
        pack_key: str,
        amount: Decimal,
        currency: str = "INR",
        return_url: str | None = None,
    ) -> CheckoutSessionResult:
        """Create one-time checkout for minute top-up pack."""
        pass

    @abstractmethod
    def cancel_subscription(self, provider_sub_id: str, at_period_end: bool = True) -> SubscriptionResult:
        """Cancel subscription immediately or at period end."""
        pass

    @abstractmethod
    def resume_subscription(self, provider_sub_id: str) -> SubscriptionResult:
        """Resume a canceled subscription if still within active period."""
        pass

    @abstractmethod
    def change_plan(self, provider_sub_id: str, new_plan_key: str, prorate: bool = True) -> SubscriptionResult:
        """Upgrade (immediate + prorated) or downgrade subscription."""
        pass

    @abstractmethod
    def get_portal_url(self, customer_id: str, return_url: str) -> str:
        """Get customer billing portal URL for managing cards and billing details."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, raw_payload: bytes, signature_header: str) -> bool:
        """Cryptographically verify webhook signature."""
        pass

    @abstractmethod
    def parse_webhook_event(self, raw_payload: bytes, headers: dict[str, str]) -> WebhookParsedEvent:
        """Verify signature and parse incoming payload into canonical WebhookParsedEvent."""
        pass
