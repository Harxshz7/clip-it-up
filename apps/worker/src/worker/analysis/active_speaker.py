"""Audio-visual active speaker association using mouth variance and diarization overlap."""
from dataclasses import dataclass, field
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


@dataclass
class SpeakerTrackAssociation:
    speaker_label: str
    track_id: int
    confidence: float
    overlap_duration_ms: int
    mouth_activity_score: float


class AudioVisualSpeakerAssociator:
    """Associates diarization speaker labels with visual face tracks."""

    def __init__(self, min_confidence_threshold: float = 0.40):
        self.min_confidence_threshold = min_confidence_threshold

    def associate_speakers_with_tracks(
        self,
        tracks: list[FaceTrackData],
        speaker_turns: list[SpeakerTurn],
    ) -> dict[str, SpeakerTrackAssociation]:
        """
        Global assignment of speaker_label -> FaceTrack using Hungarian maximum overlap & mouth energy.
        """
        if not tracks or not speaker_turns:
            return {}

        unique_speakers = sorted(list({st.speaker_label for st in speaker_turns if st.speaker_label}))
        if not unique_speakers:
            return {}

        # If only 1 speaker and 1 track, direct match
        if len(unique_speakers) == 1 and len(tracks) == 1:
            return {
                unique_speakers[0]: SpeakerTrackAssociation(
                    speaker_label=unique_speakers[0],
                    track_id=tracks[0].track_id,
                    confidence=0.95,
                    overlap_duration_ms=tracks[0].end_ms - tracks[0].start_ms,
                    mouth_activity_score=1.0,
                )
            }

        # Build affinity matrix [num_speakers, num_tracks]
        affinity = np.zeros((len(unique_speakers), len(tracks)), dtype=np.float32)

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
                    # Combined temporal overlap ratio + mouth variance bonus
                    overlap_ratio = overlap_ms / float(max(1, spk_duration))
                    affinity[s_idx, t_idx] = float(overlap_ratio * (1.0 + (mouth_var * 2.0)))

        # Solve linear sum assignment (Hungarian algorithm) for maximum affinity
        row_ind, col_ind = scipy.optimize.linear_sum_assignment(-affinity)

        associations: dict[str, SpeakerTrackAssociation] = {}

        for r, c in zip(row_ind, col_ind, strict=False):
            spk = unique_speakers[r]
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
                logger.info(f"Speaker {spk} association below threshold ({conf:.2f}), treating as unknown")

        return associations
