from datetime import datetime
from typing import Any


class BillingError(Exception):
    """Base class for all billing and subscription domain errors."""

    def __init__(self, message: str, code: str = "BILLING_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
        }


class PlanLimitExceededError(BillingError):
    """Raised when a user attempts an action exceeding their tier's quota."""

    def __init__(
        self,
        limit_type: str,
        limit_value: float | int,
        used_value: float | int,
        reset_date: datetime | str | None = None,
        upgrade_url: str = "/settings/billing",
        message: str | None = None,
    ):
        reset_iso = (
            reset_date.isoformat() if isinstance(reset_date, datetime) else (str(reset_date) if reset_date else None)
        )
        msg = (
            message
            or f"Monthly {limit_type.replace('_', ' ')} limit ({limit_value}) exceeded. Currently used: {used_value}."
        )
        super().__init__(msg, code="PLAN_LIMIT_EXCEEDED", status_code=402)
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.used_value = used_value
        self.reset_date = reset_iso
        self.upgrade_url = upgrade_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "limit_type": self.limit_type,
            "limit": self.limit_value,
            "limit_value": self.limit_value,
            "used": self.used_value,
            "used_value": self.used_value,
            "reset_date": self.reset_date,
            "upgrade_url": self.upgrade_url,
        }


class ConcurrencyLimitError(BillingError):
    """Raised when concurrent jobs exceed plan allowance."""

    def __init__(
        self,
        max_concurrent: int,
        active_count: int,
        upgrade_url: str = "/settings/billing",
        message: str | None = None,
    ):
        msg = (
            message
            or f"Maximum concurrent jobs limit ({max_concurrent}) reached. You currently have {active_count} active jobs."
        )
        super().__init__(msg, code="CONCURRENCY_LIMIT", status_code=429)
        self.max_concurrent = max_concurrent
        self.active_count = active_count
        self.upgrade_url = upgrade_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "max_concurrent": self.max_concurrent,
            "active_count": self.active_count,
            "upgrade_url": self.upgrade_url,
        }


class FileTooLongError(BillingError):
    """Raised when video duration exceeds plan maximum length."""

    def __init__(
        self,
        max_length_min: int,
        actual_length_min: float,
        upgrade_url: str = "/settings/billing",
        message: str | None = None,
    ):
        msg = (
            message
            or f"Video duration ({actual_length_min:.1f} min) exceeds plan maximum allowed length of {max_length_min} min."
        )
        super().__init__(msg, code="FILE_TOO_LONG", status_code=400)
        self.max_length_min = max_length_min
        self.actual_length_min = actual_length_min
        self.upgrade_url = upgrade_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "max_length_min": self.max_length_min,
            "actual_length_min": round(self.actual_length_min, 2),
            "upgrade_url": self.upgrade_url,
        }


class RateLimitExceededError(BillingError):
    """Raised when token bucket rate limiter trips."""

    def __init__(self, retry_after_seconds: int = 60, message: str | None = None):
        msg = message or f"Rate limit exceeded. Please retry after {retry_after_seconds} seconds."
        super().__init__(msg, code="RATE_LIMIT_EXCEEDED", status_code=429)
        self.retry_after_seconds = retry_after_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retry_after_seconds": self.retry_after_seconds,
        }


class WebhookVerificationError(BillingError):
    """Raised when webhook signature verification fails."""

    def __init__(self, message: str = "Invalid webhook signature"):
        super().__init__(message, code="INVALID_WEBHOOK_SIGNATURE", status_code=400)
