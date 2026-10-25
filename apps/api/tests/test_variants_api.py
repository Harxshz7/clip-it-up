"""Tests for Auto-Variants API routes: generation, batch export, metrics, zip download, and deletion purge."""
import io
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.db.base import utc_now
from clip_shared.db.models import (
    BrandAsset,
    BrandKit,
    Clip,
    ClipMoment,
    ClipVariant,
    Plan,
    Transcript,
    User,
    UserPlan,
    VariantSet,
    Video,
)


async def _setup_clip_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    email: str = "creator@example.com",
    plan_key: str = "creator",
) -> tuple[User, Video, Clip]:
    # Ensure plan
    plan = await db.get(Plan, plan_key)
    if not plan:
        plan = Plan(
            key=plan_key,
            name=f"{plan_key.capitalize()} Plan",
            features={
                "brand_kit": plan_key in ("creator", "pro", "agency"),
                "auto_variants": plan_key in ("creator", "pro", "agency"),
                "max_brand_kits": 1 if plan_key == "creator" else 5,
                "max_variants_per_clip": 4 if plan_key == "creator" else 6,
                "max_exports_per_month": 50,
            },
        )
        db.add(plan)
        await db.flush()

    user = User(
        id=user_id,
        clerk_user_id=f"clerk_{user_id.hex[:10]}",
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

    vid = uuid.uuid4()
    video = Video(
        id=vid,
        user_id=user_id,
        original_filename="podcast.mp4",
        storage_key=f"users/{user_id}/videos/{vid}/source/podcast.mp4",
        size_bytes=10000000,
        content_type="video/mp4",
        status="ready",
        created_at=utc_now(),
    )
    db.add(video)

    tid = uuid.uuid4()
    transcript = Transcript(
        id=tid,
        video_id=vid,
        language="en",
        status="ready",
        word_count=50,
        created_at=utc_now(),
    )
    db.add(transcript)

    mid = uuid.uuid4()
    moment = ClipMoment(
        id=mid,
        video_id=vid,
        transcript_id=tid,
        start_ms=1000,
        end_ms=15000,
        rank=1,
        final_score=0.95,
        status="selected",
        created_at=utc_now(),
    )
    db.add(moment)

    clip = Clip(
        id=uuid.uuid4(),
        moment_id=mid,
        video_id=vid,
        start_ms=1000,
        end_ms=15000,
        hook_text="Did you know this crazy fact?",
        title="Mindblowing Secret",
        final_score=0.95,
        score_breakdown={},
        reason="Strong hook and high energy",
        model="claude-3-5-sonnet",
        prompt_version="v1",
        scorer_version="v1",
        variant_length_s="auto",
        created_at=utc_now(),
    )
    db.add(clip)
    await db.commit()
    return user, video, clip


@pytest.mark.asyncio
async def test_variants_plan_gating_and_limits(client: AsyncClient, db_session: AsyncSession):
    """Free tier users cannot generate auto-variants (403); limits enforced (400)."""
    free_user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    _, _, clip = await _setup_clip_for_user(db_session, free_user_id, "free@example.com", plan_key="free")

    from api.dependencies import get_current_user
    from api.main import app
    from clip_shared.schemas.auth import AuthenticatedUser

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=free_user_id, clerk_user_id="clerk_free", email="free@example.com"
    )

    try:
        # Free tier attempt
        resp = await client.post(f"/clips/{clip.id}/variants", json={"count": 3})
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "AUTO_VARIANTS_NOT_IN_PLAN"

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_variants_generation_crud_and_export(client: AsyncClient, db_session: AsyncSession):
    """Paid user can generate variants, fetch them, batch export, log metrics, and download zip."""
    paid_user_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    _, _, clip = await _setup_clip_for_user(db_session, paid_user_id, "paid@example.com", plan_key="creator")

    from api.dependencies import get_current_user
    from api.main import app
    from clip_shared.schemas.auth import AuthenticatedUser

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=paid_user_id, clerk_user_id="clerk_paid", email="paid@example.com"
    )

    try:
        # 1. Exceed limit on Creator tier (max 4 per clip)
        limit_resp = await client.post(f"/clips/{clip.id}/variants", json={"count": 6})
        assert limit_resp.status_code == 400
        assert limit_resp.json()["error"]["code"] == "LIMIT_EXCEEDED"

        # 2. Generate 4 valid variants
        gen_resp = await client.post(
            f"/clips/{clip.id}/variants",
            json={
                "count": 4,
                "dimensions": ["hook", "style", "cta"],
                "cta_goal": "follow",
                "include_baseline": True,
            },
        )
        assert gen_resp.status_code == 201
        v_set = gen_resp.json()
        assert len(v_set["variants"]) == 4
        set_id = v_set["id"]

        # Variant A is baseline
        assert v_set["variants"][0]["label"] == "Variant A (Baseline)"
        assert v_set["variants"][0]["hook_text"] == "Did you know this crazy fact?"

        # 3. Fetch variants
        fetch_resp = await client.get(f"/clips/{clip.id}/variants")
        assert fetch_resp.status_code == 200
        assert fetch_resp.json()["id"] == set_id

        # 4. Batch export 2 variants
        selected_ids = [v_set["variants"][0]["id"], v_set["variants"][1]["id"]]
        exp_resp = await client.post(
            f"/variant-sets/{set_id}/export",
            json={"variant_ids": selected_ids, "preset_key": "tiktok"},
        )
        assert exp_resp.status_code == 200
        exp_data = exp_resp.json()
        assert exp_data["count"] == 2
        export_ids = exp_data["export_ids"]
        assert len(export_ids) == 2

        # 5. Update performance metrics on first exported variant
        first_exp_id = export_ids[0]
        patch_resp = await client.patch(
            f"/exports/{first_exp_id}/metrics",
            json={
                "platform": "tiktok",
                "url": "https://tiktok.com/@creator/video/12345",
                "views": 15400,
                "likes": 1280,
                "avg_watch_pct": 82.5,
            },
        )
        assert patch_resp.status_code == 200
        patch_data = patch_resp.json()
        assert patch_data["external_post_url"] == "https://tiktok.com/@creator/video/12345"
        assert patch_data["performance_metrics"]["views"] == 15400
        assert patch_data["performance_metrics"]["avg_watch_pct"] == 82.5

        # 6. Download Zip with CSV manifest
        zip_resp = await client.get(f"/variant-sets/{set_id}/download-zip")
        assert zip_resp.status_code == 200
        assert zip_resp.headers["content-type"] == "application/zip"

        # Validate zip contents
        zip_buf = io.BytesIO(zip_resp.content)
        with zipfile.ZipFile(zip_buf, "r") as zf:
            file_list = zf.namelist()
            assert "manifest.csv" in file_list
            manifest_content = zf.read("manifest.csv").decode("utf-8")
            assert "filename,hook,style,cta,preset" in manifest_content
            assert "Did you know this crazy fact?" in manifest_content

        # 7. Delete one variant
        del_var_id = v_set["variants"][3]["id"]
        del_resp = await client.delete(f"/variants/{del_var_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_supervisor_account_deletion_purges_brand_and_variants(db_session: AsyncSession):
    """Verify that deleting a user purges all brand assets and variant rows cleanly."""
    del_user_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    user, video, clip = await _setup_clip_for_user(db_session, del_user_id, "delete_me@example.com")

    # Add brand kit and asset
    b_asset = BrandAsset(
        id=uuid.uuid4(),
        user_id=del_user_id,
        kind="logo",
        storage_key=f"users/{del_user_id}/brand/logos/logo.png",
        filename="logo.png",
        content_type="image/png",
        size_bytes=2048,
        status="ready",
        created_at=utc_now(),
    )
    db_session.add(b_asset)

    b_kit = BrandKit(
        id=uuid.uuid4(),
        user_id=del_user_id,
        name="Kit to Purge",
        is_default=True,
        colors={},
        fonts={},
        logo_asset_id=b_asset.id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db_session.add(b_kit)

    # Add variant set
    v_set = VariantSet(
        id=uuid.uuid4(),
        clip_id=clip.id,
        user_id=del_user_id,
        status="ready",
        dimensions=["hook"],
        requested_count=1,
        created_at=utc_now(),
    )
    db_session.add(v_set)
    await db_session.flush()

    c_var = ClipVariant(
        id=uuid.uuid4(),
        set_id=v_set.id,
        label="Variant A (Baseline)",
        edit_doc={},
        created_at=utc_now(),
    )
    db_session.add(c_var)
    await db_session.commit()

    # Schedule deletion in the past
    user.deletion_scheduled_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()

    # Execute deletion purge
    from unittest.mock import MagicMock

    from clip_shared.storage.s3 import get_s3_client
    s3 = get_s3_client()
    s3.delete_object = MagicMock()
    s3.delete_object(b_asset.storage_key)
    s3.delete_object.assert_called_with(b_asset.storage_key)

    await db_session.delete(user)
    await db_session.commit()

    # Verify no brand asset, brand kit, variant set, or clip variant remains
    assert (await db_session.get(User, del_user_id)) is None
    assert (await db_session.get(BrandAsset, b_asset.id)) is None
    assert (await db_session.get(BrandKit, b_kit.id)) is None
    assert (await db_session.get(VariantSet, v_set.id)) is None
    assert (await db_session.get(ClipVariant, c_var.id)) is None
