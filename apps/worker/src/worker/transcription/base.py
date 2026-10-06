from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any


@dataclass
class WordItem:
    idx: int
    word: str
    start_ms: int
    end_ms: int
    speaker: Optional[str] = None
    confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "idx": self.idx,
            "word": self.word,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "speaker": self.speaker,
            "confidence": self.confidence,
        }


@dataclass
class SegmentItem:
    idx: int
    start_ms: int
    end_ms: int
    speaker: Optional[str]
    text: str
    words: List[WordItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "idx": self.idx,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "speaker": self.speaker,
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
        }


@dataclass
class SpeakerItem:
    label: str
    display_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "display_name": self.display_name,
        }


@dataclass
class TranscriptionResult:
    language: str
    status: str
    model: str
    backend: str
    word_count: int
    words: List[WordItem]
    segments: List[SegmentItem]
    speakers: List[SpeakerItem]
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "status": self.status,
            "model": self.model,
            "backend": self.backend,
            "word_count": self.word_count,
            "words": [w.to_dict() for w in self.words],
            "segments": [s.to_dict() for s in self.segments],
            "speakers": [sp.to_dict() for sp in self.speakers],
            "raw_response": self.raw_response,
        }


class BaseTranscriptionBackend(ABC):
    """Abstract interface for speech-to-text & diarization engines."""

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        progress_cb: Optional[Callable[[str, float], None]] = None,
    ) -> TranscriptionResult:
        """
        Transcribe the audio file and return word-level timestamps and speaker labels.
        progress_cb(sub_step_name, percent_complete) can be invoked per sub-step.
        """
        pass
