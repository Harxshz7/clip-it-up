import gc
import os
from typing import Callable, Dict, List, Optional, Any, Tuple
import structlog
from clip_shared.config import get_settings
from worker.transcription.base import (
    BaseTranscriptionBackend,
    WordItem,
    SpeakerItem,
    TranscriptionResult,
)
from worker.transcription.segment_builder import build_segments_from_words

logger = structlog.get_logger()

# Global worker singletons to load models once per worker process
_WHISPER_MODEL = None
_ALIGN_MODELS: Dict[str, Tuple[Any, Any]] = {}
_DIARIZATION_PIPELINE = None


def _cleanup_gpu_memory():
    """Clear GPU cache and run Python garbage collection."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _get_device_and_compute_type() -> Tuple[str, str]:
    """Detect available compute device (cuda vs cpu) and appropriate compute type."""
    settings = get_settings()
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
            compute_type = settings.WHISPER_COMPUTE_TYPE or "float16"
        else:
            device = "cpu"
            compute_type = "int8" if settings.WHISPER_COMPUTE_TYPE == "float16" else settings.WHISPER_COMPUTE_TYPE
    except Exception:
        device = "cpu"
        compute_type = "int8"
    return device, compute_type


def get_cached_whisper_model():
    """Load WhisperX ASR model once per process."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        import whisperx
        settings = get_settings()
        device, compute_type = _get_device_and_compute_type()
        logger.info(
            "loading_whisperx_model",
            model_name=settings.WHISPER_MODEL,
            device=device,
            compute_type=compute_type,
        )
        _WHISPER_MODEL = whisperx.load_model(
            settings.WHISPER_MODEL,
            device=device,
            compute_type=compute_type,
            language="en",
        )
    return _WHISPER_MODEL


def get_cached_align_model(language_code: str):
    """Load phoneme alignment model once per language."""
    global _ALIGN_MODELS
    if language_code not in _ALIGN_MODELS:
        import whisperx
        device, _ = _get_device_and_compute_type()
        logger.info("loading_alignment_model", language_code=language_code, device=device)
        model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
        _ALIGN_MODELS[language_code] = (model_a, metadata)
    return _ALIGN_MODELS[language_code]


def get_cached_diarization_pipeline():
    """Load PyAnnote diarization pipeline once per process."""
    global _DIARIZATION_PIPELINE
    settings = get_settings()
    if not settings.DIARIZATION_ENABLED or not settings.HF_TOKEN:
        return None

    if _DIARIZATION_PIPELINE is None:
        import whisperx
        device, _ = _get_device_and_compute_type()
        logger.info("loading_diarization_pipeline", device=device)
        _DIARIZATION_PIPELINE = whisperx.DiarizationPipeline(
            use_auth_token=settings.HF_TOKEN,
            device=device,
        )
    return _DIARIZATION_PIPELINE


class WhisperXBackend(BaseTranscriptionBackend):
    """
    Production-grade GPU WhisperX speech-to-text with phoneme alignment and speaker diarization.
    """

    def __init__(self):
        self.settings = get_settings()

    def transcribe(
        self,
        audio_path: str,
        progress_cb: Optional[Callable[[str, float], None]] = None,
    ) -> TranscriptionResult:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            import whisperx
        except ImportError as e:
            raise RuntimeError(f"whisperx is not installed in the worker environment: {e}")

        device, compute_type = _get_device_and_compute_type()

        try:
            # 1. Load Audio
            if progress_cb:
                progress_cb("load_audio", 10.0)
            logger.info("whisperx_loading_audio", audio_path=audio_path)
            audio = whisperx.load_audio(audio_path)

            # 2. Transcribe
            if progress_cb:
                progress_cb("transcribing", 30.0)
            model = get_cached_whisper_model()
            batch_size = self.settings.WHISPER_BATCH_SIZE or 16
            logger.info("whisperx_transcribing", batch_size=batch_size)
            raw_transcription = model.transcribe(audio, batch_size=batch_size)
            detected_language = raw_transcription.get("language", "en")

            # 3. Align (Word-level timestamps)
            if progress_cb:
                progress_cb("aligning", 60.0)
            logger.info("whisperx_aligning_words", language=detected_language)
            model_a, metadata = get_cached_align_model(detected_language)
            aligned_result = whisperx.align(
                raw_transcription["segments"],
                model_a,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )

            # 4. Diarize (Speaker labels)
            diarize_pipeline = get_cached_diarization_pipeline()
            if diarize_pipeline:
                if progress_cb:
                    progress_cb("diarizing", 80.0)
                logger.info("whisperx_diarizing_speakers")
                try:
                    min_spk = self.settings.MIN_SPEAKERS
                    max_spk = self.settings.MAX_SPEAKERS
                    diarize_segments = diarize_pipeline(
                        audio,
                        min_speakers=min_spk,
                        max_speakers=max_spk,
                    )
                    final_result = whisperx.assign_word_speakers(diarize_segments, aligned_result)
                except Exception as ex:
                    logger.warning("diarization_failed_fallback_default", error=str(ex))
                    final_result = aligned_result
            else:
                final_result = aligned_result

            # 5. Extract words and format
            if progress_cb:
                progress_cb("structuring_segments", 95.0)

            words: List[WordItem] = []
            speaker_set = set()
            word_counter = 0

            for seg in final_result.get("segments", []):
                seg_speaker = seg.get("speaker", "SPEAKER_00")
                if seg_speaker:
                    speaker_set.add(seg_speaker)

                seg_words = seg.get("words", [])
                for w in seg_words:
                    word_str = w.get("word", "").strip()
                    if not word_str:
                        continue
                    # Word start/end are in float seconds in WhisperX
                    start_sec = w.get("start")
                    end_sec = w.get("end")

                    # If word alignment failed on a specific token, interpolate from segment
                    if start_sec is None:
                        start_sec = seg.get("start", 0.0)
                    if end_sec is None:
                        end_sec = seg.get("end", start_sec + 0.3)

                    start_ms = int(float(start_sec) * 1000)
                    end_ms = max(start_ms + 100, int(float(end_sec) * 1000))
                    speaker = w.get("speaker") or seg_speaker or "SPEAKER_00"
                    speaker_set.add(speaker)
                    confidence = float(w.get("score", 0.95)) if w.get("score") is not None else 0.95

                    words.append(
                        WordItem(
                            idx=word_counter,
                            word=word_str,
                            start_ms=start_ms,
                            end_ms=end_ms,
                            speaker=speaker,
                            confidence=confidence,
                        )
                    )
                    word_counter += 1

            if not speaker_set:
                speaker_set.add("SPEAKER_00")

            segments = build_segments_from_words(words)
            speakers = [SpeakerItem(label=lbl) for lbl in sorted(speaker_set)]

            result = TranscriptionResult(
                language=detected_language,
                status="ready",
                model=self.settings.WHISPER_MODEL,
                backend="whisperx",
                word_count=len(words),
                words=words,
                segments=segments,
                speakers=speakers,
                raw_response=final_result,
            )

            if progress_cb:
                progress_cb("completed", 100.0)

            return result

        finally:
            # Always clean GPU memory after transcription
            _cleanup_gpu_memory()
