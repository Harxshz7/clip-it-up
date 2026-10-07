import time
import uuid
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.config import get_settings
from clip_shared.db.models import Project, User
from clip_shared.db.session import get_db
from clip_shared.schemas.auth import AuthenticatedUser

settings = get_settings()
security = HTTPBearer(auto_error=False)

# In-memory cache for Clerk JWKS
_jwks_cache: dict[str, Any] = {}
_jwks_cache_expiry: float = 0


async def get_clerk_jwks() -> dict[str, Any]:
    """Fetch and cache Clerk JWKS keys."""
    global _jwks_cache, _jwks_cache_expiry
    now = time.time()

    if _jwks_cache and now < _jwks_cache_expiry:
        return _jwks_cache

    if not settings.CLERK_JWKS_URL:
        return {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(settings.CLERK_JWKS_URL)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_cache_expiry = now + 3600  # Cache for 1 hour
            return _jwks_cache
        except Exception as e:
            if _jwks_cache:
                return _jwks_cache
            raise HTTPException(
                status_code=503,
                detail={"error": {"code": "AUTH_JWKS_UNAVAILABLE", "message": f"Unable to reach auth provider: {str(e)}"}},
            ) from e


async def get_current_user(
    request: Request,
    auth_header: HTTPAuthorizationCredentials | None = Security(security),
    token_query: str | None = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedUser:
    """
    Authenticate user via Clerk JWT Bearer token, query token (for SSE), or Dev Bypass.
    Upserts user record into PostgreSQL on first request.
    """
    token = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif token_query:
        token = token_query

    # 1. Dev Bypass check
    if not token and settings.DEV_AUTH_BYPASS:
        if settings.ENVIRONMENT != "development":
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "DEV_BYPASS_FORBIDDEN", "message": "Dev auth bypass is forbidden outside development environment."}},
            )

        dev_user_id = uuid.UUID(settings.DEV_USER_ID)

        # Ensure dev user exists in DB
        user_stmt = select(User).where(User.id == dev_user_id)
        result = await db.execute(user_stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                id=dev_user_id,
                clerk_user_id=settings.DEV_CLERK_USER_ID,
                email=settings.DEV_USER_EMAIL,
            )
            db.add(user)
            await db.flush()

            # Also create default project for dev user if not exists
            proj_stmt = select(Project).where(Project.user_id == dev_user_id)
            proj_result = await db.execute(proj_stmt)
            if not proj_result.scalar_one_or_none():
                db.add(Project(id=uuid.uuid4(), user_id=dev_user_id, name="Default Project"))
                await db.flush()

        return AuthenticatedUser(
            id=user.id,
            clerk_user_id=user.clerk_user_id,
            email=user.email,
        )

    # 2. Token verification
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing authentication credentials."}},
        )

    try:
        # Get token header to find matching key ID (kid)
        unverified_headers = jwt.get_unverified_header(token)
        kid = unverified_headers.get("kid")
        jwks = await get_clerk_jwks()

        key = None
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == kid:
                key = jwk
                break

        if not key:
            raise HTTPException(
                status_code=401,
                detail={"error": {"code": "INVALID_TOKEN", "message": "Token signing key not found."}},
            )

        verify_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
        }

        decode_kwargs: dict[str, Any] = {
            "token": token,
            "key": key,
            "algorithms": ["RS256"],
            "options": verify_options,
        }

        if settings.CLERK_ISSUER:
            decode_kwargs["issuer"] = settings.CLERK_ISSUER

        payload = jwt.decode(**decode_kwargs)

        clerk_user_id = payload.get("sub")
        if not clerk_user_id:
            raise HTTPException(
                status_code=401,
                detail={"error": {"code": "INVALID_TOKEN_CLAIMS", "message": "Token missing subject claim."}},
            )

        email = payload.get("email") or payload.get("primary_email_address") or f"{clerk_user_id}@users.clerk.dev"

        # Look up or create user
        stmt = select(User).where(User.clerk_user_id == clerk_user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                id=uuid.uuid4(),
                clerk_user_id=clerk_user_id,
                email=email,
            )
            db.add(user)
            await db.flush()

            # Create default project
            db.add(Project(id=uuid.uuid4(), user_id=user.id, name="Default Project"))
            await db.flush()

        return AuthenticatedUser(
            id=user.id,
            clerk_user_id=user.clerk_user_id,
            email=user.email,
        )

    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_TOKEN", "message": f"Token validation failed: {str(e)}"}},
        ) from e
