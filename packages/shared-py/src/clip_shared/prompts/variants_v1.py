"""Pydantic schemas and prompt templates for Auto-Variants generation."""
from pydantic import BaseModel, Field


class HookCandidate(BaseModel):
    text: str = Field(description="Attention-grabbing hook line for the first 3 seconds")
    angle: str = Field(description="question | bold_claim | intrigue | pattern_interrupt | contrarian")
    predicted_score: float = Field(default=0.85, ge=0.0, le=1.0)


class CTACandidate(BaseModel):
    text: str = Field(description="Punchy call to action under 8 words")
    goal: str = Field(description="follow | link_in_bio | subscribe | engagement")


class VariantGenerationBatchResponse(BaseModel):
    hooks: list[HookCandidate] = Field(default_factory=list)
    ctas: list[CTACandidate] = Field(default_factory=list)


def build_variant_generation_prompt(
    clip_text: str,
    original_hook: str,
    cta_goal: str = "follow",
    count: int = 4,
) -> str:
    return f"""You are a viral short-form growth strategist and video editor.
Generate high-converting alternative hooks and strong calls to action for this short video clip.

Clip Transcript / Context:
\"{clip_text}\"

Original Hook:
\"{original_hook}\"

CTA Goal:
{cta_goal} (e.g. follow, link_in_bio, subscribe, engagement)

Requirements:
1. Generate {count} unique, high-energy alternative hooks. Each hook must adopt a different psychological angle:
   - Question / curiosity gap
   - Bold claim / provocative statement
   - Pattern interrupt
   - Contrarian / counter-intuitive take
2. Generate 3 distinct calls to action strictly tailored to the goal '{cta_goal}'.
3. Keep hooks punchy, natural, and under 12 words. Keep CTAs under 8 words.
4. Return structured JSON matching the schema.
"""
