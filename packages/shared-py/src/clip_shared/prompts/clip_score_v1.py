from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class Pass1CandidateItem(BaseModel):
    id: str = Field(description="Candidate identifier")
    start_ms: int
    end_ms: int
    text: str


class Pass1CoarseScore(BaseModel):
    id: str
    coarse_score: float = Field(ge=1.0, le=10.0, description="Coarse score 1-10")
    reason: str = Field(description="Brief 1-sentence rationale")


class Pass1BatchResponse(BaseModel):
    scores: List[Pass1CoarseScore]


class ClipScoreFlags(BaseModel):
    needs_context: bool = Field(default=False, description="Requires external context to make sense")
    off_topic: bool = Field(default=False, description="Off-topic banter or rambling")
    profanity: bool = Field(default=False, description="Contains explicit profanity")
    sensitive: bool = Field(default=False, description="Sensitive, controversial, or NSFW topic")


class Pass2CandidateScore(BaseModel):
    id: str
    hook: float = Field(ge=0.0, le=1.0, description="Hook strength (0-1)")
    emotion: float = Field(ge=0.0, le=1.0, description="Emotional intensity / conviction (0-1)")
    coherence: float = Field(ge=0.0, le=1.0, description="Standalone coherence (0-1)")
    payoff: float = Field(ge=0.0, le=1.0, description="Payoff / punchline satisfaction (0-1)")
    novelty: float = Field(ge=0.0, le=1.0, description="Insight novelty / uniqueness (0-1)")
    best_hook_text: str = Field(description="The attention-grabbing first 3-seconds line")
    suggested_start_ms: int = Field(description="Refined start timestamp in milliseconds")
    suggested_end_ms: int = Field(description="Refined end timestamp in milliseconds")
    title: str = Field(description="Viral hook-driven title (3-7 words)")
    reason: str = Field(description="1-2 sentences explaining why this makes a great clip")
    flags: ClipScoreFlags = Field(default_factory=ClipScoreFlags)


def build_pass1_prompt(candidates: List[Pass1CandidateItem], video_summary: str) -> str:
    candidates_formatted = "\n\n".join(
        f"[{c.id}] ({c.start_ms/1000:.1f}s - {c.end_ms/1000:.1f}s):\n\"{c.text}\""
        for c in candidates
    )
    return f"""You are evaluating video segments to find the most viral, engaging standalone short clips.

Video Summary Context:
{video_summary}

Rate each candidate on a coarse scale of 1.0 to 10.0 based on potential virality, hook strength, and coherence.

Candidates to evaluate:
{candidates_formatted}

Return structured JSON adhering to the schema.
"""


def build_pass2_prompt(
    candidate_id: str,
    start_ms: int,
    end_ms: int,
    text: str,
    speaker: Optional[str],
    video_summary: str,
) -> str:
    return f"""You are an elite short-form video editor for TikTok, YouTube Shorts, and Instagram Reels.

Full Video Context:
{video_summary}

Evaluate this specific candidate window:
- ID: {candidate_id}
- Speaker: {speaker or 'Speaker'}
- Range: {start_ms}ms to {end_ms}ms ({start_ms/1000:.1f}s - {end_ms/1000:.1f}s)
- Transcript:
"{text}"

Evaluate hook (0-1), emotion (0-1), coherence (0-1), payoff (0-1), novelty (0-1).
Identify the best first-3-seconds hook line (`best_hook_text`).
Suggest refined boundary trims (`suggested_start_ms`, `suggested_end_ms`) within the [{start_ms}, {end_ms}] range to land squarely on the hook and cut cleanly at the resolution.
Provide a punchy title (3-7 words), a concise reason, and content flags.
Return structured JSON adhering to the schema.
"""
