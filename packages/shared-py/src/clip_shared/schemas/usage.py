from decimal import Decimal
from typing import List
from pydantic import BaseModel


class MetricSummary(BaseModel):
    metric: str
    total_quantity: Decimal
    total_cost_inr: Decimal


class UsageSummaryResponse(BaseModel):
    month: str
    total_cost_inr: Decimal
    metrics: List[MetricSummary]
