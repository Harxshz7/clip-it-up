from typing import Optional
from clip_shared.config import get_settings
from worker.transcription.base import (
    BaseTranscriptionBackend,
    WordItem,
    SegmentItem,
    SpeakerItem,
    TranscriptionResult,
)
from worker.transcription.segment_builder import build_segments_from_words
from worker.transcription.export import (
    export_txt,
    export_srt,
    export_vtt,
    export_json,
)
from worker.transcription.mock import MockTranscriptionBackend


def get_transcription_backend(backend_type: Optional[str] = None) -> BaseTranscriptionBackend:
    """Factory to get the configured transcription backend."""
    settings = get_settings()
    backend_name = (backend_type or settings.TRANSCRIBE_BACKEND).lower()

    if backend_name == "whisperx":
        try:
            from worker.transcription.whisperx_backend import WhisperXBackend
            return WhisperXBackend()
        except Exception as e:
            # If running on non-GPU environment without whisperx installed, log warning and fallback to mock if dev
            import structlog
            logger = structlog.get_logger()
            logger.warning("whisperx_import_failed_fallback", error=str(e), fallback="mock")
            return MockTranscriptionBackend()
    elif backend_name == "deepgram":
        from worker.transcription.deepgram_backend import DeepgramBackend
        return DeepgramBackend()
    elif backend_name == "mock":
        return MockTranscriptionBackend()
    else:
        return MockTranscriptionBackend()


__all__ = [
    "BaseTranscriptionBackend",
    "WordItem",
    "SegmentItem",
    "SpeakerItem",
    "TranscriptionResult",
    "build_segments_from_words",
    "export_txt",
    "export_srt",
    "export_vtt",
    "export_json",
    "MockTranscriptionBackend",
    "get_transcription_backend",
]
