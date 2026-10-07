import time
from collections.abc import Callable

from worker.transcription.base import (
    BaseTranscriptionBackend,
    SpeakerItem,
    TranscriptionResult,
    WordItem,
)
from worker.transcription.segment_builder import build_segments_from_words

MOCK_TRANSCRIPT_DIALOGUE = [
    ("SPEAKER_00", "Welcome back to the creator podcast today we are discussing short form video algorithms."),
    ("SPEAKER_01", "Thanks for having me. The most important metric right now is 3-second hook retention and watch time percentage."),
    ("SPEAKER_00", "Exactly. If viewers drop off before five seconds the distribution completely stops."),
    ("SPEAKER_01", "And dynamic word by word captions increase completion rates by over thirty percent."),
    ("SPEAKER_00", "That is why automated AI pipelines are changing how creators produce content daily."),
    ("SPEAKER_01", "You take a thirty minute conversation and turn it into ten high quality vertical clips instantly."),
]


class MockTranscriptionBackend(BaseTranscriptionBackend):
    """
    Deterministic mock transcription backend for dev and CI environments.
    Produces realistic word-level timestamps and speaker diarization.
    """

    def __init__(self, step_delay: float = 0.01):
        self.step_delay = step_delay

    def transcribe(
        self,
        audio_path: str,
        progress_cb: Callable[[str, float], None] | None = None,
    ) -> TranscriptionResult:
        sub_steps = [
            ("load_audio", 15.0),
            ("transcribe_asr", 45.0),
            ("align_words", 70.0),
            ("diarize_speakers", 90.0),
            ("finalize_segments", 100.0),
        ]

        for step_name, pct in sub_steps:
            if self.step_delay > 0:
                time.sleep(self.step_delay)
            if progress_cb:
                progress_cb(step_name, pct)

        words: list[WordItem] = []
        current_time_ms = 400
        word_idx = 0

        # Generate timed words from dialogue
        for speaker, sentence in MOCK_TRANSCRIPT_DIALOGUE:
            sentence_words = sentence.split()
            for w in sentence_words:
                duration_ms = max(220, int(len(w) * 65))
                start_ms = current_time_ms
                end_ms = start_ms + duration_ms
                current_time_ms = end_ms + 60  # small inter-word gap

                # Add punctuation to last word of sentence if not present
                formatted_word = w
                if w == sentence_words[-1] and not formatted_word.endswith((".", "!", "?")):
                    formatted_word += "."

                words.append(
                    WordItem(
                        idx=word_idx,
                        word=formatted_word,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        speaker=speaker,
                        confidence=0.96,
                    )
                )
                word_idx += 1
            current_time_ms += 500  # speaker pause

        segments = build_segments_from_words(words)
        speakers = [
            SpeakerItem(label="SPEAKER_00", display_name="Host"),
            SpeakerItem(label="SPEAKER_01", display_name="Guest"),
        ]

        raw_json = {
            "language": "en",
            "model": "mock-v1",
            "backend": "mock",
            "word_count": len(words),
            "words": [w.to_dict() for w in words],
            "segments": [s.to_dict() for s in segments],
            "speakers": [sp.to_dict() for sp in speakers],
        }

        return TranscriptionResult(
            language="en",
            status="ready",
            model="mock-v1",
            backend="mock",
            word_count=len(words),
            words=words,
            segments=segments,
            speakers=speakers,
            raw_response=raw_json,
        )
