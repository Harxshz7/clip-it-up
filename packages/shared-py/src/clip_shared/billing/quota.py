import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from clip_shared.billing.exceptions import (
    ConcurrencyLimitError,
    FileTooLongError,
    PlanLimitExceededError,
)
from clip_shared.config import load_billing_config, load_plans_config
from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    Export,
    Job,
    Plan,
    QuotaLedger,
    TopUp,
    User,
    UserPlan,
)


class QuotaService:
    """Enterprise quota calculation, reservation, reconciliation, and audit ledger."""

    @staticmethod
    def get_fallback_plan() -> Plan:
        plans_cfg = load_plans_config().get("plans", {})
        free_cfg = plans_cfg.get("free", {})
        return Plan(
            key="free",
            name=free_cfg.get("name", "Free Tier"),
            monthly_source_minutes=free_cfg.get("monthly_source_minutes", 30),
            monthly_minutes=free_cfg.get("monthly_source_minutes", 30),
            max_exports_per_month=free_cfg.get("max_exports_per_month", 10),
            watermark=free_cfg.get("watermark", True),
            export_watermark=free_cfg.get("watermark", True),
            max_export_height=free_cfg.get("max_export_height", 1920),
            max_video_length_min=free_cfg.get("max_video_length_min", 15),
            max_concurrent_jobs=free_cfg.get("max_concurrent_jobs", 1),
            retention_days=free_cfg.get("retention_days", 7),
            priority=free_cfg.get("priority", "normal"),
            features=free_cfg.get("features", {"watermark": True}),
        )

    # -----------------------------------------------------------------------
    # Async Methods (FastAPI Routes)
    # -----------------------------------------------------------------------

    @classmethod
    async def get_user_plan_and_period(cls, db: AsyncSession, user_id: uuid.UUID) -> tuple[Plan, datetime, datetime]:
        stmt = select(UserPlan).where(UserPlan.user_id == user_id)
        res = await db.execute(stmt)
        user_plan = res.scalar_one_or_none()

        plan_key = user_plan.plan_key if user_plan else "free"
        now = datetime.now(UTC)
        period_start = user_plan.period_start if user_plan else now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = user_plan.period_end if (user_plan and user_plan.period_end) else period_start + timedelta(days=30)

        # Plan details
        p_stmt = select(Plan).where(Plan.key == plan_key)
        p_res = await db.execute(p_stmt)
        plan = p_res.scalar_one_or_none()
        if not plan:
            plan = cls.get_fallback_plan()

        return plan, period_start, period_end

    @classmethod
    async def get_ledger_balance(cls, db: AsyncSession, user_id: uuid.UUID) -> Decimal:
        """Calculate user's current minute balance from the append-only ledger."""
        stmt = (
            select(QuotaLedger.balance_after)
            .where(QuotaLedger.user_id == user_id)
            .order_by(QuotaLedger.created_at.desc(), QuotaLedger.id.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        latest_balance = res.scalar_one_or_none()
        if latest_balance is not None:
            return Decimal(str(latest_balance))

        # Sum of deltas invariant check if no latest row found
        sum_stmt = select(func.coalesce(func.sum(QuotaLedger.delta_minutes), Decimal("0.0000"))).where(
            QuotaLedger.user_id == user_id
        )
        sum_res = await db.execute(sum_stmt)
        return Decimal(str(sum_res.scalar() or "0.0000"))

    @classmethod
    async def get_active_top_up_minutes(cls, db: AsyncSession, user_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        stmt = select(func.coalesce(func.sum(TopUp.remaining_minutes), 0)).where(
            TopUp.user_id == user_id,
            TopUp.status == "active",
            TopUp.expires_at > now,
        )
        res = await db.execute(stmt)
        return int(res.scalar() or 0)

    @classmethod
    async def get_monthly_usage_stats(cls, db: AsyncSession, user_id: uuid.UUID, period_start: datetime) -> tuple[float, int, int]:
        """Compute used source minutes, reserved minutes, and used exports in current period."""
        # 1. Used source minutes from usage table
        from clip_shared.db.models import Usage
        src_stmt = select(func.coalesce(func.sum(Usage.quantity), Decimal("0.00"))).where(
            Usage.user_id == user_id,
            Usage.metric == "source_minutes",
            Usage.created_at >= period_start,
        )
        src_res = await db.execute(src_stmt)
        used_source_minutes = float(src_res.scalar() or 0.0)

        # 2. Exports count
        exp_stmt = select(func.count(Export.id)).where(
            Export.user_id == user_id,
            Export.status.in_(["queued", "rendering", "succeeded"]),
            Export.created_at >= period_start,
        )
        exp_res = await db.execute(exp_stmt)
        exports_used = int(exp_res.scalar() or 0)

        # 3. Active running jobs
        job_stmt = select(func.count(Job.id)).where(
            Job.user_id == user_id,
            Job.status.in_(["queued", "running"]),
        )
        job_res = await db.execute(job_stmt)
        active_jobs_count = int(job_res.scalar() or 0)

        return used_source_minutes, exports_used, active_jobs_count

    @classmethod
    async def check_quota(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        action: str,
        amount: float = 1.0,
        video_duration_minutes: float | None = None,
    ) -> None:
        """
        Server-side quota enforcement.
        Actions:
          - 'source_minutes': checks duration, concurrency, and available minutes.
          - 'export': checks monthly export quota.
        """
        plan, period_start, period_end = await cls.get_user_plan_and_period(db, user_id)
        used_minutes, used_exports, active_jobs = await cls.get_monthly_usage_stats(db, user_id, period_start)
        topup_minutes = await cls.get_active_top_up_minutes(db, user_id)
        total_allowed_minutes = plan.monthly_source_minutes + topup_minutes

        # Check Concurrency
        if action in ("source_minutes", "job_start"):
            if active_jobs >= plan.max_concurrent_jobs:
                raise ConcurrencyLimitError(
                    max_concurrent=plan.max_concurrent_jobs,
                    active_count=active_jobs,
                    upgrade_url="/settings/billing",
                )

        # Check File Duration Length
        if video_duration_minutes is not None:
            if video_duration_minutes > plan.max_video_length_min:
                raise FileTooLongError(
                    max_length_min=plan.max_video_length_min,
                    actual_length_min=video_duration_minutes,
                    upgrade_url="/settings/billing",
                )

        # Check Source Minutes
        if action in ("source_minutes", "job_start"):
            if used_minutes + amount > total_allowed_minutes:
                billing_cfg = load_billing_config()
                overage_policy = billing_cfg.get("billing_policy", {}).get("overage_policy", "block")
                if overage_policy == "block":
                    raise PlanLimitExceededError(
                        limit_type="monthly_source_minutes",
                        limit_value=total_allowed_minutes,
                        used_value=round(used_minutes, 2),
                        reset_date=period_end,
                        upgrade_url="/settings/billing",
                        message=f"Source minutes limit reached ({total_allowed_minutes} min). Currently used: {used_minutes:.1f} min. Upgrade or buy a top-up pack to continue.",
                    )

        # Check Exports Count
        if action == "export":
            if used_exports + int(amount) > plan.max_exports_per_month:
                raise PlanLimitExceededError(
                    limit_type="max_exports_per_month",
                    limit_value=plan.max_exports_per_month,
                    used_value=used_exports,
                    reset_date=period_end,
                    upgrade_url="/settings/billing",
                    message=f"Monthly export limit ({plan.max_exports_per_month}) reached for plan '{plan.name}'. Upgrade to export more clips.",
                )

    @classmethod
    async def reserve_minutes(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        minutes: float,
        reason: str = "job_reserve",
    ) -> QuotaLedger:
        """Reserve minutes at job initiation into the append-only ledger."""
        delta = -Decimal(str(round(minutes, 4)))
        current_bal = await cls.get_ledger_balance(db, user_id)
        new_bal = current_bal + delta

        entry = QuotaLedger(
            id=uuid.uuid4(),
            user_id=user_id,
            delta_minutes=delta,
            balance_after=new_bal,
            reason=reason,
            ref_id=str(job_id),
            meta={"job_id": str(job_id), "reserved_minutes": minutes},
            created_at=utc_now(),
        )
        db.add(entry)
        await db.flush()
        return entry

    @classmethod
    async def refund_minutes(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        minutes: float,
        reason: str = "job_system_failure_refund",
    ) -> QuotaLedger:
        """Automatically refund reserved quota when a job fails for system reasons."""
        delta = Decimal(str(round(minutes, 4)))
        current_bal = await cls.get_ledger_balance(db, user_id)
        new_bal = current_bal + delta

        entry = QuotaLedger(
            id=uuid.uuid4(),
            user_id=user_id,
            delta_minutes=delta,
            balance_after=new_bal,
            reason=reason,
            ref_id=str(job_id),
            meta={"job_id": str(job_id), "refunded_minutes": minutes},
            created_at=utc_now(),
        )
        db.add(entry)
        await db.flush()
        return entry

    # -----------------------------------------------------------------------
    # Synchronous Methods (Celery Beat & Worker Pipeline)
    # -----------------------------------------------------------------------

    @classmethod
    def get_ledger_balance_sync(cls, db: Session, user_id: uuid.UUID) -> Decimal:
        latest = (
            db.query(QuotaLedger.balance_after)
            .filter(QuotaLedger.user_id == user_id)
            .order_by(QuotaLedger.created_at.desc(), QuotaLedger.id.desc())
            .first()
        )
        if latest is not None:
            return Decimal(str(latest[0]))

        total = db.query(func.coalesce(func.sum(QuotaLedger.delta_minutes), Decimal("0.0000"))).filter(
            QuotaLedger.user_id == user_id
        ).scalar()
        return Decimal(str(total or "0.0000"))

    @classmethod
    def refund_minutes_sync(
        cls,
        db: Session,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        minutes: float,
        reason: str = "job_system_failure_refund",
    ) -> QuotaLedger:
        delta = Decimal(str(round(minutes, 4)))
        current_bal = cls.get_ledger_balance_sync(db, user_id)
        new_bal = current_bal + delta

        entry = QuotaLedger(
            id=uuid.uuid4(),
            user_id=user_id,
            delta_minutes=delta,
            balance_after=new_bal,
            reason=reason,
            ref_id=str(job_id),
            meta={"job_id": str(job_id), "refunded_minutes": minutes},
            created_at=utc_now(),
        )
        db.add(entry)
        db.flush()
        return entry

    @classmethod
    def reconcile_minutes_sync(
        cls,
        db: Session,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        reserved_minutes: float,
        actual_minutes: float,
    ) -> QuotaLedger | None:
        """Reconcile difference between reserved estimate and measured actual video duration."""
        diff = round(reserved_minutes - actual_minutes, 4)
        if abs(diff) < 0.0001:
            return None

        delta = Decimal(str(diff))  # If diff > 0, we reserved too much, refund excess to user
        current_bal = cls.get_ledger_balance_sync(db, user_id)
        new_bal = current_bal + delta

        entry = QuotaLedger(
            id=uuid.uuid4(),
            user_id=user_id,
            delta_minutes=delta,
            balance_after=new_bal,
            reason="job_reconcile",
            ref_id=str(job_id),
            meta={
                "job_id": str(job_id),
                "reserved": reserved_minutes,
                "actual": actual_minutes,
                "adjustment": float(delta),
            },
            created_at=utc_now(),
        )
        db.add(entry)
        db.flush()
        return entry

    @classmethod
    def record_grant_sync(
        cls,
        db: Session,
        user_id: uuid.UUID,
        minutes: float,
        reason: str = "monthly_renewal",
        ref_id: str | None = None,
    ) -> QuotaLedger:
        delta = Decimal(str(round(minutes, 4)))
        current_bal = cls.get_ledger_balance_sync(db, user_id)
        new_bal = current_bal + delta

        entry = QuotaLedger(
            id=uuid.uuid4(),
            user_id=user_id,
            delta_minutes=delta,
            balance_after=new_bal,
            reason=reason,
            ref_id=ref_id,
            meta={"granted_minutes": minutes},
            created_at=utc_now(),
        )
        db.add(entry)
        db.flush()
        return entry
