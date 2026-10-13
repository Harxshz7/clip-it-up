from clip_shared.billing.fake_provider import FakeBillingProvider
from clip_shared.billing.provider import BillingProvider
from clip_shared.billing.razorpay_provider import RazorpayBillingProvider
from clip_shared.billing.stripe_provider import StripeBillingProvider
from clip_shared.config import get_settings

settings = get_settings()


def get_billing_provider(
    provider_name: str | None = None,
    currency: str = "INR",
    country: str = "IN",
) -> BillingProvider:
    """
    Factory returning the appropriate BillingProvider.
    - If explicit provider requested ('razorpay', 'stripe', 'fake'), use it.
    - Otherwise, route by currency / country:
      - INR or India -> Razorpay (Primary)
      - Non-INR (e.g. USD) -> Stripe (if PROVIDER_STRIPE_ENABLED), else fallback to Razorpay international
    """
    selected = provider_name.lower() if provider_name else None

    if selected == "fake":
        return FakeBillingProvider()

    if selected == "stripe":
        if not settings.PROVIDER_STRIPE_ENABLED:
            # Fall back to Razorpay if Stripe not enabled
            return RazorpayBillingProvider()
        return StripeBillingProvider()

    if selected == "razorpay":
        return RazorpayBillingProvider()

    # Route based on currency & country
    if currency.upper() == "USD" and settings.PROVIDER_STRIPE_ENABLED:
        return StripeBillingProvider()

    # Default provider for India (INR)
    return RazorpayBillingProvider()
