"""Tests for Phase 7a database models, relationships, and bidirectional mappings."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clip_shared.db.models import (
    BrandAsset,
    BrandKit,
    Clip,
    ClipMoment,
    ClipVariant,
    Export,
    Transcript,
    User,
    VariantSet,
    Video,
)


@pytest.mark.asyncio
async def test_export_variant_bidirectional_relationship(db_session: AsyncSession):
    # 1. Create user, video, transcript, moment, clip
    user = User(
        id=uuid.uuid4(),
        clerk_user_id=f"user_brand_{uuid.uuid4().hex[:8]}",
        email="brand_test@clipitup.local",
    )
    video = Video(
        id=uuid.uuid4(),
        user=user,
        original_filename="podcast.mp4",
        storage_key="videos/podcast.mp4",
        size_bytes=5_000_000,
        content_type="video/mp4",
    )
    transcript = Transcript(
        id=uuid.uuid4(),
        video=video,
        status="ready",
        language="en",
    )
    moment = ClipMoment(
        id=uuid.uuid4(),
        video=video,
        transcript=transcript,
        start_ms=1000,
        end_ms=25000,
    )
    clip = Clip(
        id=uuid.uuid4(),
        video=video,
        moment=moment,
        start_ms=1000,
        end_ms=25000,
        hook_text="Did you know about brand kits?",
        title="Brand Kit Spotlight",
        final_score=9.2,
        reason="Strong hook and concise takeaway",
        model="claude-3-haiku",
        prompt_version="v1",
        scorer_version="v1",
    )

    # 2. Create VariantSet and ClipVariant
    variant_set = VariantSet(
        id=uuid.uuid4(),
        clip=clip,
        user=user,
        status="ready",
        dimensions=["hook", "style", "cta"],
        requested_count=4,
    )
    variant = ClipVariant(
        id=uuid.uuid4(),
        variant_set=variant_set,
        edit_doc={"version": 1, "preset_key": "tiktok"},
        label="Variant A (Bold Pop)",
        hook_text="Alternative hook line",
        caption_style_key="bold_pop",
        cta_text="Follow for more tips",
        cta_style="pill",
        score_hint=9.4,
    )

    # 3. Create Export with variant link
    export = Export(
        id=uuid.uuid4(),
        clip=clip,
        user=user,
        status="succeeded",
        preset_key="tiktok",
        params_snapshot={"version": 1, "preset": "tiktok"},
        variant=variant,
        external_post_url="https://tiktok.com/@creator/video/123",
        performance_metrics={"views": 5000, "likes": 420},
    )

    db_session.add_all([user, video, transcript, moment, clip, variant_set, variant, export])
    await db_session.commit()

    # 4. Read back and verify both sides of relationship
    stmt_exp = select(Export).where(Export.id == export.id)
    exp_res = await db_session.execute(stmt_exp)
    loaded_export = exp_res.scalar_one()

    assert loaded_export.variant is not None
    assert loaded_export.variant.id == variant.id
    assert loaded_export.variant.label == "Variant A (Bold Pop)"

    stmt_var = select(ClipVariant).where(ClipVariant.id == variant.id)
    var_res = await db_session.execute(stmt_var)
    loaded_variant = var_res.scalar_one()

    assert loaded_variant.export is not None
    assert loaded_variant.export.id == export.id
    assert loaded_variant.export.status == "succeeded"
    assert loaded_variant.export.performance_metrics == {"views": 5000, "likes": 420}


@pytest.mark.asyncio
async def test_brand_kit_and_asset_lifecycle(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        clerk_user_id=f"user_kit_{uuid.uuid4().hex[:8]}",
        email="kit_test@clipitup.local",
    )
    logo = BrandAsset(
        id=uuid.uuid4(),
        user=user,
        kind="logo",
        storage_key="brand/logo.png",
        filename="logo.png",
        content_type="image/png",
        size_bytes=150_000,
        width=512,
        height=512,
        status="ready",
        metadata_json={"has_alpha": True},
    )
    intro = BrandAsset(
        id=uuid.uuid4(),
        user=user,
        kind="intro",
        storage_key="brand/intro.mp4",
        filename="intro.mp4",
        content_type="video/mp4",
        size_bytes=2_000_000,
        width=1080,
        height=1920,
        duration_ms=3000,
        status="ready",
        metadata_json={"fps": 30.0},
    )
    kit = BrandKit(
        id=uuid.uuid4(),
        user=user,
        name="Creator Studio Kit",
        is_default=True,
        colors={"primary": "#6366f1", "secondary": "#ec4899", "text": "#ffffff"},
        fonts={"heading_asset_id": None, "font_family": "Inter"},
        logo_asset=logo,
        logo_position="top_right",
        logo_opacity=0.9,
        logo_scale=0.15,
        caption_style_key="bold_pop",
        intro_asset=intro,
        outro_asset=None,
        watermark_free_override=True,
    )
    db_session.add_all([user, logo, intro, kit])
    await db_session.commit()

    stmt = select(BrandKit).where(BrandKit.id == kit.id)
    res = await db_session.execute(stmt)
    loaded_kit = res.scalar_one()

    assert loaded_kit.name == "Creator Studio Kit"
    assert loaded_kit.logo_asset is not None
    assert loaded_kit.logo_asset.storage_key == "brand/logo.png"
    assert loaded_kit.intro_asset is not None
    assert loaded_kit.intro_asset.duration_ms == 3000
    assert loaded_kit.is_default is True
