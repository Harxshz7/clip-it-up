"""Server-side subscription plan limits and usage validation."""
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from clip_shared.db.models import Export, Plan, Usage, UserPlan


class PlanLimitExceededError(Exception):
    def __init__(self, message: str, limit_type: str, limit_value: Any, current_value: Any, reset_date: str):
        super().__init__(message)
        self.code = "PLAN_LIMIT_EXCEEDED"
        self.message = message
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.current_value = current_value
        self.reset_date = reset_date

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.code,
            "message": self.message,
            "limit_type": self.limit_type,
            "limit_value": self.limit_value,
            "current_value": self.current_value,
            "reset_date": self.reset_date,
        }


def compute_params_snapshot_hash(params: dict[str, Any]) -> str:
    """Deterministic SHA-256 hash of export parameters snapshot."""
    clean_params = {k: v for k, v in params.items() if k not in ("hash", "created_at")}
    serialized = json.dumps(clean_params, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_user_plan_and_usage(user_id: uuid.UUID, db: Session) -> dict[str, Any]:
    """
    Get active user plan, billing period start, and calculate monthly usage.
    """
    user_plan = db.query(UserPlan).filter(UserPlan.user_id == user_id).first()
    plan_key = user_plan.plan_key if user_plan else "free"
    period_start = user_plan.period_start if user_plan else datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0)

    plan = db.query(Plan).filter(Plan.key == plan_key).first()
    if not plan:
        # Fallback to default free plan if not in DB yet
        plan = Plan(
            key="free",
            name="Free Tier",
            monthly_minutes=30,
            export_watermark=True,
            max_export_height=1920,
            max_exports_per_month=10,
            features={"watermark": True, "max_resolution": "1080p"},
        )

    # 1. Calculate monthly source minutes processed
    source_min_query = db.query(func.coalesce(func.sum(Usage.quantity), 0)).filter(
        Usage.user_id == user_id,
        Usage.metric == "source_minutes",
        Usage.created_at >= period_start,
    ).scalar()
    source_min_used = float(source_min_query or 0.0)

    # 2. Calculate monthly exports completed / in progress
    exports_count_query = db.query(func.count(Export.id)).filter(
        Export.user_id == user_id,
        Export.status.in_(["queued", "rendering", "succeeded"]),
        Export.created_at >= period_start,
    ).scalar()
    exports_used = int(exports_count_query or 0)

    return {
        "plan": plan,
        "period_start": period_start,
        "monthly_source_minutes_used": source_min_used,
        "monthly_exports_used": exports_used,
        "monthly_source_minutes_limit": plan.monthly_minutes,
        "monthly_exports_limit": plan.max_exports_per_month,
        "watermark_required": plan.export_watermark,
    }


def enforce_export_plan_limits(user_id: uuid.UUID, db: Session, admin_override: bool = False) -> None:
    """
    Validate that user has not exceeded their monthly export quota.
    Raises PlanLimitExceededError if over limit.
    """
    if admin_override:
        return

    usage_info = get_user_plan_and_usage(user_id, db)
    plan: Plan = usage_info["plan"]
    exports_used = usage_info["monthly_exports_used"]
    period_start: datetime = usage_info["period_start"]

    # Calculate next reset date (approx 30 days after period_start)
    reset_date_str = period_start.strftime("%Y-%m-%d")

    if exports_used >= plan.max_exports_per_month:
        raise PlanLimitExceededError(
            message=f"Monthly export limit ({plan.max_exports_per_month}) reached for plan '{plan.name}'. Please upgrade to Creator or Pro to export more clips.",
            limit_type="max_exports_per_month",
            limit_value=plan.max_exports_per_month,
            current_value=exports_used,
            reset_date=reset_date_str,
        )
