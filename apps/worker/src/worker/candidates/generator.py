import math
import uuid
from typing import List, Dict, Any, Optional
import structlog
from sqlalchemy.orm import Session

from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import ClipMoment, TranscriptSegment, TranscriptWord, Video, Transcript
from worker.candidates.window_generator import generate_candidate_windows, CandidateWindow
from worker.candidates.filters import filter_candidate_windows, cluster_and_deduplicate_candidates

logger = structlog.get_logger()
settings = get_settings()


def run_candidate_generation(
    video_id: uuid.UUID,
    transcript_id: uuid.UUID,
    db: Session,
    single_speaker_mode: bool = False,
    max_candidates_override: Optional[int] = None,
) -> List[CandidateWindow]:
    """
    Candidate stage pipeline:
    1. Fetch transcript segments and words from DB.
    2. Generate sliding sentence-boundary windows (15s - 90s).
    3. Filter out low quality windows (topic shift, fillers, silence, speaker purity).
    4. Cluster overlapping windows (IoU > 0.5) and keep best per cluster.
    5. Persist candidates into clip_moments table (status='candidate').
    """
    # 1. Fetch segments
    segments_rows = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.transcript_id == transcript_id)
        .order_by(TranscriptSegment.idx)
        .all()
    )
    segments = [
        {
            "idx": s.idx,
            "start_ms": s.start_ms,
            "end_ms": s.end_ms,
            "speaker": s.speaker,
            "text": s.text,
        }
        for s in segments_rows
    ]

    # Fetch words
    words_rows = (
        db.query(TranscriptWord)
        .filter(TranscriptWord.transcript_id == transcript_id)
        .order_by(TranscriptWord.idx)
        .all()
    )
    words = [
        {
            "idx": w.idx,
            "start_ms": w.start_ms,
            "end_ms": w.end_ms,
            "word": w.word,
            "speaker": w.speaker,
        }
        for w in words_rows
    ]

    if not segments:
        logger.warning("no_segments_found_for_candidate_generation", video_id=str(video_id))
        return []

    # Calculate target candidate cap based on duration
    total_duration_s = (segments[-1]["end_ms"] - segments[0]["start_ms"]) / 1000.0
    duration_hours = max(0.1, total_duration_s / 3600.0)
    
    if max_candidates_override is not None:
        target_max_candidates = max_candidates_override
    else:
        target_max_candidates = max(10, int(settings.MAX_CANDIDATES_PER_HOUR * duration_hours))

    logger.info(
        "generating_candidate_windows",
        segments_count=len(segments),
        words_count=len(words),
        duration_s=total_duration_s,
        max_candidates=target_max_candidates,
    )

    # 2. Generate raw windows
    raw_windows = generate_candidate_windows(segments, min_length_s=15.0, max_length_s=90.0)
    logger.info("raw_windows_generated", count=len(raw_windows))

    # 3. Apply Quality Guardrails
    filtered_windows = filter_candidate_windows(
        raw_windows,
        words=words,
        segments=segments,
        require_single_speaker=single_speaker_mode,
    )
    logger.info("filtered_windows_count", count=len(filtered_windows))

    # Fallback if filters were overly strict
    if not filtered_windows and raw_windows:
        filtered_windows = raw_windows

    # 4. Deduplicate and Cluster
    final_candidates = cluster_and_deduplicate_candidates(
        filtered_windows,
        iou_threshold=0.50,
        max_candidates=target_max_candidates,
    )
    logger.info("final_candidates_selected", count=len(final_candidates))

    # 5. Idempotent Database Persistence (replace existing candidate moments if re-run)
    existing_moments = (
        db.query(ClipMoment)
        .filter(ClipMoment.video_id == video_id, ClipMoment.status == "candidate")
        .all()
    )
    for m in existing_moments:
        db.delete(m)
    db.flush()

    for idx, cand in enumerate(final_candidates):
        moment = ClipMoment(
            id=uuid.uuid4(),
            video_id=video_id,
            transcript_id=transcript_id,
            start_ms=cand.start_ms,
            end_ms=cand.end_ms,
            rank=idx + 1,
            final_score=cand.heuristic_score,
            status="candidate",
            created_at=utc_now(),
        )
        db.add(moment)

    db.flush()
    return final_candidates
