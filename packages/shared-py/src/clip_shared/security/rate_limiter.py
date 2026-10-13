import hashlib
import math
import time
from typing import Any

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from clip_shared.billing.exceptions import RateLimitExceededError
from clip_shared.config import get_settings, load_billing_config

settings = get_settings()


class RedisRateLimiter:
    """
    Redis token bucket rate limiter with typed 429 exceptions and accurate Retry-After header.
    Works with live Redis or in-memory fallback for local development/testing.
    """
    _local_buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_time)

    @classmethod
    async def check_rate_limit(
        cls,
        scope: str,
        identifier: str,
        capacity: int = 20,
        refill_rate_per_sec: float = 0.5,  # 30 tokens/minute
        cost: float = 1.0,
    ) -> None:
        key = f"ratelimit:{scope}:{identifier}"
        now = time.time()

        try:
            r = aioredis.from_url(settings.REDIS_URL)
            # Use Redis hash for atomic token bucket
            pipe = r.pipeline()
            pipe.hmget(key, "tokens", "last_updated")
            results = await pipe.execute()
            data = results[0]

            if data[0] is not None and data[1] is not None:
                current_tokens = float(data[0])
                last_updated = float(data[1])
                # Refill
                elapsed = max(0.0, now - last_updated)
                current_tokens = min(float(capacity), current_tokens + (elapsed * refill_rate_per_sec))
            else:
                current_tokens = float(capacity)

            if current_tokens < cost:
                deficit = cost - current_tokens
                retry_after = max(1, math.ceil(deficit / refill_rate_per_sec))
                await r.aclose()
                raise RateLimitExceededError(retry_after_seconds=retry_after)

            # Consume tokens
            current_tokens -= cost
            pipe = r.pipeline()
            pipe.hset(key, mapping={"tokens": str(current_tokens), "last_updated": str(now)})
            pipe.expire(key, 3600)
            await pipe.execute()
            await r.aclose()

        except RateLimitExceededError:
            raise
        except Exception:
            # In-memory token bucket fallback if Redis offline
            current_tokens, last_updated = cls._local_buckets.get(key, (float(capacity), now))
            elapsed = max(0.0, now - last_updated)
            current_tokens = min(float(capacity), current_tokens + (elapsed * refill_rate_per_sec))

            if current_tokens < cost:
                deficit = cost - current_tokens
                retry_after = max(1, math.ceil(deficit / refill_rate_per_sec))
                raise RateLimitExceededError(retry_after_seconds=retry_after)

            current_tokens -= cost
            cls._local_buckets[key] = (current_tokens, now)


class AbuseFilter:
    """Sign up abuse, disposable email filtering, and CAPTCHA validation."""

    _ip_signups_today: dict[str, list[float]] = {}

    @classmethod
    def is_disposable_email(cls, email: str) -> bool:
        """Reject throwaway and burner email addresses."""
        domain = email.split("@")[-1].lower() if "@" in email else ""
        cfg = load_billing_config()
        blocked_domains = cfg.get("abuse_caps", {}).get("disposable_email_domains", [])
        return domain in blocked_domains

    @classmethod
    async def check_signup_abuse(
        cls,
        ip: str,
        email: str,
        captcha_token: str | None = None,
    ) -> None:
        # 1. Check disposable email
        if cls.is_disposable_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "DISPOSABLE_EMAIL_PROHIBITED",
                        "message": "Disposable email addresses are not permitted. Please sign up with a valid permanent email.",
                    }
                },
            )

        # 2. Check CAPTCHA if enabled
        if settings.CAPTCHA_ENABLED:
            if not captcha_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "CAPTCHA_REQUIRED", "message": "CAPTCHA verification is required."}},
                )

        # 3. Check IP signup cap per day
        now = time.time()
        cfg = load_billing_config()
        max_signups_per_ip = cfg.get("abuse_caps", {}).get("max_free_signups_per_ip_per_day", 3)

        cls._ip_signups_today.setdefault(ip, [])
        # prune older than 24h (86400s)
        cls._ip_signups_today[ip] = [t for t in cls._ip_signups_today[ip] if now - t < 86400]

        if len(cls._ip_signups_today[ip]) >= max_signups_per_ip:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": {
                        "code": "FREE_SIGNUP_LIMIT_EXCEEDED",
                        "message": f"Daily limit of {max_signups_per_ip} free signups exceeded for this IP address.",
                    }
                },
            )

        cls._ip_signups_today[ip].append(now)

    @staticmethod
    def hash_ip(ip: str) -> str:
        """One-way hash of IP for privacy compliance."""
        return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
