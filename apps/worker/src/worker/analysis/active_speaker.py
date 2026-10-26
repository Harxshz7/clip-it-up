"""Audio-visual active speaker association using mouth variance, temporal diarization overlap, and Hungarian assignment."""
from dataclasses import dataclass
from typing import Any

import numpy as np
import scipy.optimize
import structlog

from worker.analysis.tracker import FaceTrackData

logger = structlog.get_logger()


@dataclass
class SpeakerTurn:
    start_ms: int
    end_ms: int
    speaker_label: str
    is_laughter: bool = False


@dataclass
class SpeakerTrackAssociation:
    speaker_label: str
    track_id: int | None
    confidence: float
    overlap_duration_ms: int
    mouth_activity_score: float
    is_offscreen: bool = False


class AudioVisualSpeakerAssociator:
    """
    Associates N diarization speaker labels with N visual face tracks.
    Supports 3-6 faces, local mouth motion correlation, unknown/off-screen speaker handling,
    and confidence scoring.
    """

    def __init__(self, min_confidence_threshold: float = 0.35):
        self.min_confidence_threshold = min_confidence_threshold

    def associate_speakers_with_tracks(
        self,
        tracks: list[FaceTrackData],
        speaker_turns: list[SpeakerTurn],
    ) -> dict[str, SpeakerTrackAssociation]:
        """
        Global assignment of speaker_label -> FaceTrack using Hungarian maximum overlap & mouth energy.
        Gracefully handles unknown/off-screen speakers and arbitrary N speakers / N tracks.
        """
        if not speaker_turns:
            return {}

        unique_speakers = sorted(list({st.speaker_label for st in speaker_turns if st.speaker_label}))
        if not unique_speakers:
            return {}

        if not tracks:
            # All speakers are off-screen
            return {
                spk: SpeakerTrackAssociation(
                    speaker_label=spk,
                    track_id=None,
                    confidence=0.0,
                    overlap_duration_ms=0,
                    mouth_activity_score=0.0,
                    is_offscreen=True,
                )
                for spk in unique_speakers
            }

        # If 1 speaker and 1 track, direct match
        if len(unique_speakers) == 1 and len(tracks) == 1:
            trk = tracks[0]
            trk.speaker_label = unique_speakers[0]
            return {
                unique_speakers[0]: SpeakerTrackAssociation(
                    speaker_label=unique_speakers[0],
                    track_id=trk.track_id,
                    confidence=0.95,
                    overlap_duration_ms=trk.end_ms - trk.start_ms,
                    mouth_activity_score=trk.summary.get("mouth_variance", 0.0),
                )
            }

        # Build affinity matrix [num_speakers, num_tracks]
        num_spk = len(unique_speakers)
        num_trk = len(tracks)
        affinity = np.zeros((num_spk, num_trk), dtype=np.float32)

        for s_idx, spk in enumerate(unique_speakers):
            turns = [st for st in speaker_turns if st.speaker_label == spk]
            spk_duration = sum(st.end_ms - st.start_ms for st in turns)

            for t_idx, trk in enumerate(tracks):
                overlap_ms = 0
                for st in turns:
                    ov = max(0, min(st.end_ms, trk.end_ms) - max(st.start_ms, trk.start_ms))
                    overlap_ms += ov

                if overlap_ms > 0:
                    mouth_var = trk.summary.get("mouth_variance", 0.0)
                    mouth_mean = trk.summary.get("mouth_mean", 0.0)
                    overlap_ratio = overlap_ms / float(max(1, spk_duration))

                    # Bonus for mouth movement during speech turn
                    mouth_bonus = 1.0 + min(2.0, (mouth_var * 5.0) + (mouth_mean * 1.5))
                    affinity[s_idx, t_idx] = float(overlap_ratio * mouth_bonus)

        # Solve linear sum assignment (Hungarian algorithm) for maximum affinity
        # Pad affinity to square if num_spk != num_trk for robust assignment
        dim = max(num_spk, num_trk)
        cost_matrix = np.full((dim, dim), 1e5, dtype=np.float32)
        cost_matrix[:num_spk, :num_trk] = -affinity

        row_ind, col_ind = scipy.optimize.linear_sum_assignment(cost_matrix)

        associations: dict[str, SpeakerTrackAssociation] = {}

        for r, c in zip(row_ind, col_ind, strict=False):
            if r >= num_spk:
                continue
            spk = unique_speakers[r]

            if c < num_trk:
                trk = tracks[c]
                score = float(affinity[r, c])
                conf = min(1.0, max(0.0, score))

                if conf >= self.min_confidence_threshold:
                    associations[spk] = SpeakerTrackAssociation(
                        speaker_label=spk,
                        track_id=trk.track_id,
                        confidence=conf,
                        overlap_duration_ms=trk.end_ms - trk.start_ms,
                        mouth_activity_score=trk.summary.get("mouth_variance", 0.0),
                    )
                    trk.speaker_label = spk
                else:
                    # Below threshold: treat speaker as unknown/off-screen
                    logger.info(f"Speaker {spk} affinity below threshold ({conf:.2f}), treating as off-screen/unknown")
                    associations[spk] = SpeakerTrackAssociation(
                        speaker_label=spk,
                        track_id=None,
                        confidence=conf,
                        overlap_duration_ms=0,
                        mouth_activity_score=0.0,
                        is_offscreen=True,
                    )
            else:
                # Unassigned speaker (more speakers than tracks)
                associations[spk] = SpeakerTrackAssociation(
                    speaker_label=spk,
                    track_id=None,
                    confidence=0.0,
                    overlap_duration_ms=0,
                    mouth_activity_score=0.0,
                    is_offscreen=True,
                )

        return associations
