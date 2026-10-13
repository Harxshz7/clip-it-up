from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    description: str | None = None
    price_inr_monthly: int
    price_usd_monthly: int
    monthly_source_minutes: int
    max_exports_per_month: int
    watermark: bool
    max_video_length_min: int
    max_concurrent_jobs: int
    retention_days: int
    priority: str
    is_active: bool
    is_public: bool
    features: dict[str, Any] = Field(default_factory=dict)


class TopUpPackDetail(BaseModel):
    key: str
    name: str
    minutes: int
    price_inr: int
    price_usd: int
    validity_days: int


class CheckoutRequest(BaseModel):
    plan_key: str
    currency: str = "INR"
    country: str = "IN"
    return_url: str | None = None


class TopUpRequest(BaseModel):
    pack_key: str
    currency: str = "INR"
    return_url: str | None = None


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    provider: str
    currency: str
    amount: Decimal
    plan_key: str


class ChangePlanRequest(BaseModel):
    new_plan_key: str
    prorate: bool = True


class BillingMeResponse(BaseModel):
    plan: PlanDetail
    subscription_status: str  # active | past_due | canceled | free | expired
    provider: str | None = None
    period_start: datetime
    period_end: datetime | None = None
    monthly_source_minutes_used: float
    monthly_source_minutes_limit: int
    monthly_exports_used: int
    monthly_exports_limit: int
    top_up_minutes_available: int
    ledger_balance_minutes: float
    cancel_at_period_end: bool = False
    watermark_required: bool = True


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_number: str
    financial_year: str
    type: str  # tax_invoice | receipt | credit_note
    taxable_amount: Decimal
    total_tax: Decimal
    total_amount: Decimal
    currency: str
    place_of_supply: str
    status: str
    pdf_download_url: str | None = None
    created_at: datetime
