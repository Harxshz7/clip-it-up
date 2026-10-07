import os
from collections.abc import Callable
from typing import Any

import httpx
import structlog

from clip_shared.config import get_settings
from worker.transcription.base import (
    BaseTranscriptionBackend,
    SpeakerItem,
    TranscriptionResult,
    WordItem,
)
from worker.transcription.segment_builder import build_segments_from_words

logger = structlog.get_logger()


class DeepgramBackend(BaseTranscriptionBackend):
    """
    Thin adapter for Deepgram Nova-2 API.
    Maps Deepgram's word timestamps and diarization into unified TranscriptionResult.
    """

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.DEEPGRAM_API_KEY

    def transcribe(
        self,
        audio_path: str,
        progress_cb: Callable[[str, float], None] | None = None,
    ) -> TranscriptionResult:
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY is not configured.")

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if progress_cb:
            progress_cb("reading_audio", 10.0)

        url = "https://api.deepgram.com/v1/listen?model=nova-2&diarize=true&punctuate=true&utterances=true&smart_format=true"
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }

        if progress_cb:
            progress_cb("sending_request", 30.0)

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        with httpx.Client(timeout=300.0) as client:
            resp = client.post(url, headers=headers, content=audio_bytes)

        if resp.status_code != 200:
            logger.error("deepgram_api_error", status_code=resp.status_code, body=resp.text)
            raise RuntimeError(f"Deepgram API request failed with status {resp.status_code}: {resp.text}")

        if progress_cb:
            progress_cb("parsing_response", 80.0)

        data = resp.json()
        result = self.map_deepgram_response(data)

        if progress_cb:
            progress_cb("completed", 100.0)

        return result

    @classmethod
    def map_deepgram_response(cls, data: dict[str, Any]) -> TranscriptionResult:
        """Parse raw Deepgram JSON payload into unified schema."""
        results = data.get("results", {})
        channels = results.get("channels", [])
        if not channels:
            return TranscriptionResult(
                language="en",
                status="ready",
                model="nova-2",
                backend="deepgram",
                word_count=0,
                words=[],
                segments=[],
                speakers=[],
                raw_response=data,
            )

        alt = channels[0].get("alternatives", [{}])[0]
        raw_words = alt.get("words", [])
        language = alt.get("languages", ["en"])[0] if alt.get("languages") else "en"

        words: list[WordItem] = []
        speaker_labels = set()

        for idx, w in enumerate(raw_words):
            word_str = w.get("punctuated_word") or w.get("word") or ""
            start_ms = int(float(w.get("start", 0)) * 1000)
            end_ms = int(float(w.get("end", 0)) * 1000)
            speaker_int = w.get("speaker")
            speaker_label = f"SPEAKER_{speaker_int:02d}" if speaker_int is not None else "SPEAKER_00"
            speaker_labels.add(speaker_label)
            confidence = float(w.get("confidence", 1.0))

            words.append(
                WordItem(
                    idx=idx,
                    word=word_str,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    speaker=speaker_label,
                    confidence=confidence,
                )
            )

        segments = build_segments_from_words(words)
        speakers = [SpeakerItem(label=lbl) for lbl in sorted(speaker_labels)]

        return TranscriptionResult(
            language=language,
            status="ready",
            model="nova-2",
            backend="deepgram",
            word_count=len(words),
            words=words,
            segments=segments,
            speakers=speakers,
            raw_response=data,
        )
