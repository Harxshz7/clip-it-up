import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from clip_shared.billing.factory import get_billing_provider
from clip_shared.billing.invoicing import InvoiceService
from clip_shared.billing.quota import QuotaService
from clip_shared.billing.webhook_handler import WebhookHandler
from clip_shared.config import get_settings, load_plans_config
from clip_shared.db.base import utc_now
from clip_shared.db.models import Customer, Invoice, Plan, Subscription, UserPlan
from clip_shared.db.session import get_db
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.billing import (
    BillingMeResponse,
    ChangePlanRequest,
    CheckoutRequest,
    CheckoutResponse,
    InvoiceItemResponse,
    PlanDetail,
    TopUpPackDetail,
    TopUpRequest,
)

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()


@router.get("/plans")
async def list_available_plans(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """List all publicly available subscription plans and top-up minute packs."""
    plans_cfg = load_plans_config()
    configured_plans = plans_cfg.get("plans", {})
    top_ups = plans_cfg.get("top_up_packs", {})

    # Fetch from DB to ensure freshest records
    stmt = select(Plan).where(Plan.is_active == True)
    res = await db.execute(stmt)
    db_plans = res.scalars().all()

    plan_list = []
    for p in db_plans:
        if p.is_public:
            plan_list.append(PlanDetail.model_validate(p))

    topup_list = [TopUpPackDetail.model_validate(t) for t in top_ups.values()]

    return {
        "plans": plan_list,
        "top_up_packs": topup_list,
        "supported_currencies": ["INR", "USD"] if settings.PROVIDER_STRIPE_ENABLED else ["INR"],
        "stripe_enabled": settings.PROVIDER_STRIPE_ENABLED,
    }


@router.get("/me", response_model=BillingMeResponse)
async def get_my_billing_profile(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get authenticated user's current subscription, usage meters, reset date, and balances."""
    plan, period_start, period_end = await QuotaService.get_user_plan_and_period(db, user.id)
    used_min, used_exp, _ = await QuotaService.get_monthly_usage_stats(db, user.id, period_start)
    topup_min = await QuotaService.get_active_top_up_minutes(db, user.id)
    ledger_bal = await QuotaService.get_ledger_balance(db, user.id)

    # Active subscription
    sub_stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "past_due", "canceled"]),
        )
        .order_by(desc(Subscription.created_at))
    )
    sub_res = await db.execute(sub_stmt)
    sub = sub_res.scalars().first()

    up_stmt = select(UserPlan).where(UserPlan.user_id == user.id)
    up_res = await db.execute(up_stmt)
    user_plan = up_res.scalar_one_or_none()

    sub_status = sub.status if sub else ("free" if plan.key == "free" else "active")
    cancel_at_end = user_plan.cancel_at_period_end if user_plan else False

    return BillingMeResponse(
        plan=PlanDetail.model_validate(plan),
        subscription_status=sub_status,
        provider=sub.provider if sub else None,
        period_start=period_start,
        period_end=period_end,
        monthly_source_minutes_used=used_min,
        monthly_source_minutes_limit=plan.monthly_source_minutes,
        monthly_exports_used=used_exp,
        monthly_exports_limit=plan.max_exports_per_month,
        top_up_minutes_available=topup_min,
        ledger_balance_minutes=float(ledger_bal),
        cancel_at_period_end=cancel_at_end,
        watermark_required=plan.watermark,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    payload: CheckoutRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initialize hosted checkout for upgrading to Creator or Pro."""
    provider = get_billing_provider(currency=payload.currency, country=payload.country)

    # Fetch or create customer
    cust_stmt = select(Customer).where(Customer.user_id == user.id, Customer.provider == provider.name)
    cust_res = await db.execute(cust_stmt)
    cust = cust_res.scalar_one_or_none()

    if not cust:
        prov_cust_id = provider.create_customer(str(user.id), user.email, user.email.split("@")[0])
        cust = Customer(
            id=uuid.uuid4(),
            user_id=user.id,
            provider=provider.name,
            provider_customer_id=prov_cust_id,
        )
        db.add(cust)
        await db.flush()

    checkout_res = provider.create_checkout(
        user_id=str(user.id),
        customer_id=cust.provider_customer_id,
        plan_key=payload.plan_key,
        currency=payload.currency,
        return_url=payload.return_url,
    )

    return CheckoutResponse(
        checkout_url=checkout_res.checkout_url,
        session_id=checkout_res.session_id,
        provider=checkout_res.provider,
        currency=checkout_res.currency,
        amount=checkout_res.amount,
        plan_key=checkout_res.plan_key,
    )


@router.post("/top-up", response_model=CheckoutResponse)
async def create_top_up_session(
    payload: TopUpRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Purchase a one-off top-up minute pack."""
    plans_cfg = load_plans_config()
    pack = plans_cfg.get("top_up_packs", {}).get(payload.pack_key)
    if not pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PACK_NOT_FOUND", "message": f"Top-up pack '{payload.pack_key}' not found."}},
        )

    provider = get_billing_provider(currency=payload.currency)
    amount = (
        Decimal(str(pack.get("price_inr", 399)))
        if payload.currency == "INR"
        else Decimal(str(pack.get("price_usd", 5)))
    )

    # Fetch customer
    cust_stmt = select(Customer).where(Customer.user_id == user.id, Customer.provider == provider.name)
    cust_res = await db.execute(cust_stmt)
    cust = cust_res.scalar_one_or_none()
    cust_id = cust.provider_customer_id if cust else f"cust_{uuid.uuid4().hex[:8]}"

    checkout_res = provider.create_top_up_checkout(
        user_id=str(user.id),
        customer_id=cust_id,
        pack_key=payload.pack_key,
        amount=amount,
        currency=payload.currency,
        return_url=payload.return_url,
    )

    return CheckoutResponse(
        checkout_url=checkout_res.checkout_url,
        session_id=checkout_res.session_id,
        provider=checkout_res.provider,
        currency=checkout_res.currency,
        amount=checkout_res.amount,
        plan_key=checkout_res.plan_key,
    )


@router.post("/subscriptions/cancel")
async def cancel_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel subscription at period end."""
    sub_stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status == "active",
        )
        .order_by(desc(Subscription.created_at))
    )
    sub_res = await db.execute(sub_stmt)
    sub = sub_res.scalars().first()

    if not sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NO_ACTIVE_SUBSCRIPTION", "message": "No active subscription found to cancel."}},
        )

    provider = get_billing_provider(sub.provider)
    res = provider.cancel_subscription(sub.provider_subscription_id, at_period_end=True)

    sub.status = "canceled"
    sub.cancel_at_period_end = True
    sub.canceled_at = utc_now()

    up_stmt = select(UserPlan).where(UserPlan.user_id == user.id)
    up_res = await db.execute(up_stmt)
    user_plan = up_res.scalar_one_or_none()
    if user_plan:
        user_plan.status = "canceled"
        user_plan.cancel_at_period_end = True
        user_plan.canceled_at = utc_now()

    await db.commit()
    return {"status": "canceled", "access_until": sub.current_period_end.isoformat()}


@router.post("/subscriptions/resume")
async def resume_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume a canceled subscription before the period expires."""
    sub_stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status == "canceled",
        )
        .order_by(desc(Subscription.created_at))
    )
    sub_res = await db.execute(sub_stmt)
    sub = sub_res.scalars().first()

    if not sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "NO_CANCELED_SUBSCRIPTION",
                    "message": "No canceled subscription available to resume.",
                }
            },
        )

    provider = get_billing_provider(sub.provider)
    provider.resume_subscription(sub.provider_subscription_id)

    sub.status = "active"
    sub.cancel_at_period_end = False
    sub.canceled_at = None

    up_stmt = select(UserPlan).where(UserPlan.user_id == user.id)
    up_res = await db.execute(up_stmt)
    user_plan = up_res.scalar_one_or_none()
    if user_plan:
        user_plan.status = "active"
        user_plan.cancel_at_period_end = False

    await db.commit()
    return {"status": "active"}


@router.post("/subscriptions/change-plan")
async def change_subscription_plan(
    payload: ChangePlanRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upgrade immediately (prorated) or change subscription tier."""
    sub_stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "canceled"]),
        )
        .order_by(desc(Subscription.created_at))
    )
    sub_res = await db.execute(sub_stmt)
    sub = sub_res.scalars().first()

    if not sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NO_SUBSCRIPTION", "message": "Please subscribe to a plan first."}},
        )

    provider = get_billing_provider(sub.provider)
    provider.change_plan(sub.provider_subscription_id, payload.new_plan_key, prorate=payload.prorate)

    sub.plan_key = payload.new_plan_key
    sub.status = "active"
    sub.cancel_at_period_end = False

    up_stmt = select(UserPlan).where(UserPlan.user_id == user.id)
    up_res = await db.execute(up_stmt)
    user_plan = up_res.scalar_one_or_none()
    if user_plan:
        user_plan.plan_key = payload.new_plan_key
        user_plan.status = "active"
        user_plan.cancel_at_period_end = False

    await db.commit()
    return {"status": "updated", "new_plan_key": payload.new_plan_key}


@router.get("/invoices", response_model=list[InvoiceItemResponse])
async def list_user_invoices(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List historical tax invoices and receipts with download links."""
    stmt = select(Invoice).where(Invoice.user_id == user.id).order_by(desc(Invoice.created_at))
    res = await db.execute(stmt)
    invoices = res.scalars().all()

    items = []
    for inv in invoices:
        items.append(
            InvoiceItemResponse(
                id=str(inv.id),
                invoice_number=inv.invoice_number,
                financial_year=inv.financial_year,
                type=inv.type,
                taxable_amount=inv.taxable_amount,
                total_tax=inv.total_tax,
                total_amount=inv.total_amount,
                currency=inv.currency,
                place_of_supply=inv.place_of_supply,
                status=inv.status,
                pdf_download_url=f"/billing/invoices/{inv.id}/download",
                created_at=inv.created_at,
            )
        )
    return items


@router.get("/invoices/{invoice_id}/download")
async def download_invoice_pdf(
    invoice_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream binary PDF or presigned URL for tax invoice download."""
    stmt = select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user.id)
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "INVOICE_NOT_FOUND", "message": "Invoice not found."}},
        )

    seller_cfg = load_billing_config().get("seller", {})
    pdf_bytes = InvoiceService.generate_invoice_pdf(invoice, seller_cfg)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )


@router.post("/webhooks/{provider}")
async def handle_billing_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Public ingress for Razorpay and Stripe webhooks with cryptographic validation."""
    raw_payload = await request.body()
    headers = dict(request.headers)

    res = await WebhookHandler.process_event(
        db=db,
        provider_name=provider,
        raw_payload=raw_payload,
        headers=headers,
    )
    return res
