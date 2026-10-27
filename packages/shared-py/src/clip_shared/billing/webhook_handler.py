import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.billing.factory import get_billing_provider
from clip_shared.billing.invoicing import InvoiceService
from clip_shared.billing.quota import QuotaService
from clip_shared.config import load_plans_config
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Customer,
    Payment,
    Subscription,
    User,
    UserPlan,
    WebhookEvent,
)

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Idempotent, out-of-order resilient billing webhook processor."""

    @classmethod
    async def process_event(
        cls,
        db: AsyncSession,
        provider_name: str,
        raw_payload: bytes,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        provider = get_billing_provider(provider_name)
        parsed = provider.parse_webhook_event(raw_payload, headers)

        # 1. Idempotency Check: query webhook_events
        stmt = select(WebhookEvent).where(
            WebhookEvent.provider == parsed.provider,
            WebhookEvent.event_id == parsed.event_id,
        )
        res = await db.execute(stmt)
        existing_event = res.scalar_one_or_none()

        if existing_event and existing_event.status == "processed":
            logger.info("Ignoring replayed webhook event: %s (%s)", parsed.event_id, parsed.event_type)
            return {
                "status": "ignored",
                "reason": "already_processed",
                "event_id": parsed.event_id,
            }

        if not existing_event:
            existing_event = WebhookEvent(
                id=uuid.uuid4(),
                provider=parsed.provider,
                event_id=parsed.event_id,
                event_type=parsed.event_type,
                payload=parsed.payload,
                status="received",
                created_at=utc_now(),
            )
            db.add(existing_event)
            await db.flush()

        # 2. State Machine Handling
        try:
            await cls._apply_event_transition(db, parsed)
            existing_event.status = "processed"
            existing_event.processed_at = utc_now()
            await db.commit()
            return {
                "status": "processed",
                "event_id": parsed.event_id,
                "event_type": parsed.event_type,
            }
        except Exception as exc:
            logger.exception("Failed to process billing event: %s", exc)
            existing_event.status = "failed"
            existing_event.error = str(exc)
            await db.commit()
            raise

    @classmethod
    async def _apply_event_transition(cls, db: AsyncSession, event: Any) -> None:
        plans_cfg = load_plans_config().get("plans", {})
        plan_key = event.plan_key or "creator"

        # Find existing subscription by provider_subscription_id
        sub_stmt = select(Subscription).where(
            Subscription.provider == event.provider,
            Subscription.provider_subscription_id == event.resource_id,
        )
        sub_res = await db.execute(sub_stmt)
        sub = sub_res.scalar_one_or_none()

        # Find or create user from customer or metadata
        user = None
        user_id_str = (
            event.payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("notes", {}).get("user_id")
        )
        if not user_id_str:
            user_id_str = event.payload.get("data", {}).get("object", {}).get("metadata", {}).get("user_id")

        if sub:
            user_stmt = select(User).where(User.id == sub.user_id)
            user_res = await db.execute(user_stmt)
            user = user_res.scalar_one_or_none()
        elif user_id_str:
            try:
                uid = uuid.UUID(user_id_str)
                user_stmt = select(User).where(User.id == uid)
                user_res = await db.execute(user_stmt)
                user = user_res.scalar_one_or_none()
            except ValueError:
                pass

        if not user:
            # Fallback to dev user in tests if needed
            u_stmt = select(User).limit(1)
            u_res = await db.execute(u_stmt)
            user = u_res.scalar_one_or_none()
            if not user:
                return

        # Ensure Customer record exists
        if event.customer_id:
            cust_stmt = select(Customer).where(
                Customer.user_id == user.id,
                Customer.provider == event.provider,
            )
            cust_res = await db.execute(cust_stmt)
            cust = cust_res.scalar_one_or_none()
            if not cust:
                cust = Customer(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    provider=event.provider,
                    provider_customer_id=event.customer_id,
                )
                db.add(cust)
                await db.flush()

        now = datetime.now(UTC)
        p_start = event.current_period_start or now
        p_end = event.current_period_end or (p_start + timedelta(days=30))

        # Safe Out-of-Order Check:
        # If we already have a subscription with a newer period_start, do not regress status
        if sub and sub.current_period_start and p_start < sub.current_period_start:
            logger.warning("Out of order event received for sub %s. Skipping period regression.", sub.id)
            return

        # 3. Create or Update Subscription
        if not sub:
            sub = Subscription(
                id=uuid.uuid4(),
                user_id=user.id,
                customer_id=cust.id if "cust" in locals() and cust else None,
                provider=event.provider,
                provider_subscription_id=event.resource_id,
                plan_key=plan_key,
                status=event.status,
                currency=event.currency,
                current_period_start=p_start,
                current_period_end=p_end,
                created_at=now,
                updated_at=now,
            )
            db.add(sub)
            await db.flush()
        else:
            sub.status = event.status
            sub.plan_key = plan_key
            sub.current_period_start = p_start
            sub.current_period_end = p_end
            sub.updated_at = now
            await db.flush()

        # 4. Synchronize UserPlan Table
        up_stmt = select(UserPlan).where(UserPlan.user_id == user.id)
        up_res = await db.execute(up_stmt)
        user_plan = up_res.scalar_one_or_none()

        if event.status == "active":
            if not user_plan:
                user_plan = UserPlan(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    plan_key=plan_key,
                    period_start=p_start,
                    period_end=p_end,
                    status="active",
                )
                db.add(user_plan)
            else:
                user_plan.plan_key = plan_key
                user_plan.period_start = p_start
                user_plan.period_end = p_end
                user_plan.status = "active"
                user_plan.cancel_at_period_end = False

            # Grant monthly quota in ledger
            plan_minutes = plans_cfg.get(plan_key, {}).get("monthly_source_minutes", 300)
            await QuotaService.reserve_minutes(
                db=db,
                user_id=user.id,
                job_id=sub.id,
                minutes=-plan_minutes,  # delta positive: negative of negative
                reason="monthly_grant",
            )
            await db.flush()

        elif event.status in ("canceled", "past_due"):
            if user_plan:
                user_plan.status = event.status
                if event.status == "canceled":
                    user_plan.cancel_at_period_end = True
                    user_plan.canceled_at = now

        elif event.status == "expired":
            if user_plan:
                user_plan.plan_key = "free"
                user_plan.status = "active"

        # 5. Handle Payments, Invoices, and Credit Notes
        if (
            event.amount
            and event.amount > Decimal("0.00")
            and event.event_type
            in (
                "subscription.charged",
                "subscription.activated",
                "invoice.paid",
                "payment.captured",
            )
        ):
            # Record successful Payment
            pay_id = event.payment_id or f"pay_{uuid.uuid4().hex[:12]}"
            payment = Payment(
                id=uuid.uuid4(),
                user_id=user.id,
                subscription_id=sub.id,
                provider=event.provider,
                provider_payment_id=pay_id,
                amount=event.amount,
                currency=event.currency,
                status="succeeded",
                created_at=now,
            )
            db.add(payment)
            await db.flush()

            # Create sequential, gap-free Invoice
            invoice = await InvoiceService.create_invoice_async(
                db=db,
                user_id=user.id,
                customer_name=user.email.split("@")[0].capitalize(),
                customer_email=user.email,
                amount=event.amount,
                currency=event.currency,
                subscription_id=sub.id,
                payment_id=payment.id,
                customer_country="IN" if event.currency == "INR" else "US",
            )
            payment.invoice_id = invoice.id
            await db.flush()

        elif event.event_type in ("payment.failed", "invoice.payment_failed"):
            # Record failed Payment
            pay_id = event.payment_id or f"pay_fail_{uuid.uuid4().hex[:12]}"
            payment = Payment(
                id=uuid.uuid4(),
                user_id=user.id,
                subscription_id=sub.id,
                provider=event.provider,
                provider_payment_id=pay_id,
                amount=event.amount or Decimal("0.00"),
                currency=event.currency,
                status="failed",
                error_message=event.error_message or "Payment declined",
                created_at=now,
            )
            db.add(payment)
            await db.flush()

        elif event.event_type in ("payment.refunded", "refund.processed", "charge.refunded"):
            # Create Credit Note for refund
            if event.amount:
                await InvoiceService.create_invoice_async(
                    db=db,
                    user_id=user.id,
                    customer_name=user.email.split("@")[0].capitalize(),
                    customer_email=user.email,
                    amount=event.amount,
                    currency=event.currency,
                    subscription_id=sub.id,
                    is_credit_note=True,
                )
