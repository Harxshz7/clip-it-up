from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.db.session import get_db
from clip_shared.db.models import Usage
from clip_shared.schemas.auth import AuthenticatedUser
from clip_shared.schemas.usage import UsageSummaryResponse, MetricSummary
from api.dependencies import get_current_user

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated usage metrics and INR costs for current billing month for the authenticated user.
    """
    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month
    month_str = now.strftime("%Y-%m")

    # Group by metric for current month
    stmt = (
        select(
            Usage.metric,
            func.sum(Usage.quantity).label("total_quantity"),
            func.sum(Usage.cost_inr).label("total_cost_inr"),
        )
        .where(
            Usage.user_id == user.id,
            extract("year", Usage.created_at) == current_year,
            extract("month", Usage.created_at) == current_month,
        )
        .group_by(Usage.metric)
    )

    result = await db.execute(stmt)
    rows = result.all()

    metrics = []
    grand_total_cost = Decimal("0.0000")

    for row in rows:
        metric_name = row.metric
        tot_qty = Decimal(str(row.total_quantity or "0"))
        tot_cost = Decimal(str(row.total_cost_inr or "0"))
        grand_total_cost += tot_cost

        metrics.append(
            MetricSummary(
                metric=metric_name,
                total_quantity=tot_qty,
                total_cost_inr=tot_cost,
            )
        )

    return UsageSummaryResponse(
        month=month_str,
        total_cost_inr=grand_total_cost,
        metrics=metrics,
    )
