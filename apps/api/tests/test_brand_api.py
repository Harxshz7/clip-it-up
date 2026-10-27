"""Tests for Phase 7a Brand Kit & Brand Assets API routes: ownership, plan gating, quotas, and upload."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.db.base import utc_now
from clip_shared.db.models import Plan, User, UserPlan


async def _create_user_with_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    email: str,
    plan_key: str = "creator",
) -> User:
    # Ensure plan exists in DB
    plan = await db.get(Plan, plan_key)
    if not plan:
        plan = Plan(
            key=plan_key,
            name=f"{plan_key.capitalize()} Plan",
            features={
                "brand_kit": plan_key in ("creator", "pro", "agency"),
                "max_brand_kits": 1 if plan_key == "creator" else (5 if plan_key == "pro" else 0),
                "max_brand_asset_size_mb": 25 if plan_key == "creator" else (50 if plan_key == "pro" else 5),
                "max_intro_outro_length_s": 5 if plan_key == "creator" else (10 if plan_key == "pro" else 0),
                "auto_variants": plan_key in ("creator", "pro", "agency"),
                "max_variants_per_clip": 4 if plan_key == "creator" else 6,
            },
        )
        db.add(plan)
        await db.flush()

    user = User(
        id=user_id,
        clerk_user_id=f"clerk_{user_id.hex[:12]}",
        email=email,
    )
    db.add(user)
    await db.flush()

    up = UserPlan(
        id=uuid.uuid4(),
        user_id=user_id,
        plan_key=plan_key,
        period_start=utc_now(),
        status="active",
    )
    db.add(up)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_brand_kit_plan_gating(client: AsyncClient, db_session: AsyncSession):
    """Free tier users must be blocked with 403 BRAND_KIT_NOT_IN_PLAN."""
    free_user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    await _create_user_with_plan(db_session, free_user_id, "free@example.com", plan_key="free")

    # Override current user to free user
    from api.dependencies import get_current_user
    from api.main import app
    from clip_shared.schemas.auth import AuthenticatedUser

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=free_user_id, clerk_user_id="clerk_free", email="free@example.com"
    )

    try:
        # 1. Attempt to list brand kits
        resp = await client.get("/brand-kits")
        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["code"] == "BRAND_KIT_NOT_IN_PLAN"

        # 2. Attempt to create brand kit
        resp = await client.post("/brand-kits", json={"name": "My Studio"})
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "BRAND_KIT_NOT_IN_PLAN"

        # 3. Attempt to get upload URL
        resp = await client.post(
            "/brand-assets/upload-url",
            json={"filename": "logo.png", "content_type": "image/png", "size_bytes": 1024, "kind": "logo"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "BRAND_KIT_NOT_IN_PLAN"

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_brand_kit_crud_and_default(client: AsyncClient, db_session: AsyncSession):
    """Paid users can create, update, set default, and delete brand kits."""
    paid_user_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    await _create_user_with_plan(db_session, paid_user_id, "creator@example.com", plan_key="creator")

    from api.dependencies import get_current_user
    from api.main import app
    from clip_shared.schemas.auth import AuthenticatedUser

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=paid_user_id, clerk_user_id="clerk_creator", email="creator@example.com"
    )

    try:
        # Create Kit 1
        create_resp = await client.post(
            "/brand-kits",
            json={
                "name": "Acme Brand",
                "is_default": True,
                "colors": {
                    "primary": "#FF0000",
                    "secondary": "#00FF00",
                    "text": "#FFFFFF",
                    "highlight": "#FFFF00",
                    "background": "#000000",
                },
                "logo_position": "top_right",
                "logo_opacity": 0.85,
                "logo_scale": 0.2,
            },
        )
        assert create_resp.status_code == 201
        kit1 = create_resp.json()
        assert kit1["name"] == "Acme Brand"
        assert kit1["is_default"] is True
        assert kit1["colors"]["primary"] == "#FF0000"
        kit1_id = kit1["id"]

        # Get default brand kit
        def_resp = await client.get("/brand-kits/default")
        assert def_resp.status_code == 200
        assert def_resp.json()["id"] == kit1_id

        # Update kit
        upd_resp = await client.put(
            f"/brand-kits/{kit1_id}",
            json={"name": "Acme Studios Renamed", "logo_opacity": 0.95},
        )
        assert upd_resp.status_code == 200
        assert upd_resp.json()["name"] == "Acme Studios Renamed"
        assert upd_resp.json()["logo_opacity"] == 0.95

        # Quota check on Creator tier (max 1 brand kit)
        quota_resp = await client.post("/brand-kits", json={"name": "Second Kit"})
        assert quota_resp.status_code == 400
        assert quota_resp.json()["error"]["code"] == "LIMIT_EXCEEDED"

        # Delete kit
        del_resp = await client.delete(f"/brand-kits/{kit1_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True

        # Now default kit returns 404
        def_after_resp = await client.get("/brand-kits/default")
        assert def_after_resp.status_code == 404

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_brand_asset_upload_and_validation(client: AsyncClient, db_session: AsyncSession):
    """Test asset presigned URL generation, size validation, and font license checks."""
    user_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    await _create_user_with_plan(db_session, user_id, "pro@example.com", plan_key="pro")

    from api.dependencies import get_current_user
    from api.main import app
    from clip_shared.schemas.auth import AuthenticatedUser

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=user_id, clerk_user_id="clerk_pro", email="pro@example.com"
    )

    try:
        # File size exceeds limit (50MB for Pro)
        too_big_bytes = 60 * 1024 * 1024
        resp = await client.post(
            "/brand-assets/upload-url",
            json={"filename": "huge.mp4", "content_type": "video/mp4", "size_bytes": too_big_bytes, "kind": "intro"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "LIMIT_EXCEEDED"

        # Valid upload URL
        resp = await client.post(
            "/brand-assets/upload-url",
            json={"filename": "custom_font.ttf", "content_type": "font/ttf", "size_bytes": 1024 * 500, "kind": "font"},
        )
        assert resp.status_code == 200
        asset_info = resp.json()
        assert "upload_url" in asset_info
        asset_id = asset_info["asset_id"]

        # Complete without font license acknowledgment -> must fail 400
        comp_fail = await client.post(
            f"/brand-assets/{asset_id}/complete",
            json={"license_acknowledged": False},
        )
        assert comp_fail.status_code == 400
        assert comp_fail.json()["error"]["code"] == "ASSET_INVALID"

        # Complete with font license acknowledgment -> success
        comp_success = await client.post(
            f"/brand-assets/{asset_id}/complete",
            json={"license_acknowledged": True},
        )
        assert comp_success.status_code == 200
        assert comp_success.json()["id"] == asset_id

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_brand_ownership_isolation(client: AsyncClient, db_session: AsyncSession):
    """User B cannot access or modify User A's brand kit or brand asset (404)."""
    user_a = uuid.UUID("44444444-4444-4444-4444-444444444444")
    user_b = uuid.UUID("55555555-5555-5555-5555-555555555555")
    await _create_user_with_plan(db_session, user_a, "user_a@example.com", plan_key="creator")
    await _create_user_with_plan(db_session, user_b, "user_b@example.com", plan_key="creator")

    from api.dependencies import get_current_user
    from api.main import app
    from clip_shared.schemas.auth import AuthenticatedUser

    # Act as User A to create kit
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=user_a, clerk_user_id="clerk_a", email="user_a@example.com"
    )
    kit_resp = await client.post("/brand-kits", json={"name": "User A Private Kit"})
    assert kit_resp.status_code == 201
    kit_id = kit_resp.json()["id"]

    # Now switch to User B
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=user_b, clerk_user_id="clerk_b", email="user_b@example.com"
    )

    try:
        # User B accessing User A's kit must 404
        get_resp = await client.get(f"/brand-kits/{kit_id}")
        assert get_resp.status_code == 404

        # User B updating User A's kit must 404
        put_resp = await client.put(f"/brand-kits/{kit_id}", json={"name": "Hacked"})
        assert put_resp.status_code == 404

        # User B deleting User A's kit must 404
        del_resp = await client.delete(f"/brand-kits/{kit_id}")
        assert del_resp.status_code == 404

    finally:
        app.dependency_overrides.pop(get_current_user, None)
