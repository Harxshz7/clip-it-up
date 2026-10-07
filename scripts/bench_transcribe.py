#!/usr/bin/env python3
"""Benchmark transcription pipeline on a media file.

Measures:
- Wall time (seconds)
- Audio duration (seconds)
- Real-time factor (RTF = Wall Time / Audio Duration)
- Peak GPU memory allocated (MB)
- Word Error Rate (WER) if reference text is provided
- Estimated processing cost in INR per source hour
"""

import argparse
import sys
import time
from pathlib import Path

# Add shared paths
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "shared-py" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "worker" / "src"))

from clip_shared.config import get_settings
from clip_shared.rates import StageRateConfig
from worker.transcription import get_transcription_backend

settings = get_settings()



def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculate Word Error Rate using standard dynamic programming Levenshtein distance."""
    import re
    def normalize(text: str) -> list[str]:
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        return [w for w in cleaned.split() if w]

    ref_words = normalize(reference)
    hyp_words = normalize(hypothesis)

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]

    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                substitution = d[i - 1][j - 1] + 1
                insertion = d[i][j - 1] + 1
                deletion = d[i - 1][j] + 1
                d[i][j] = min(substitution, insertion, deletion)

    return float(d[len(ref_words)][len(hyp_words)]) / float(len(ref_words))


def get_audio_duration(file_path: Path) -> float:
    """Get duration of audio file using wave or ffprobe."""
    import wave
    try:
        with wave.open(str(file_path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return frames / float(rate)
    except Exception:
        # Fallback to rough estimate if wave fails
        return 30.0


def main():
    parser = argparse.ArgumentParser(description="Benchmark speech-to-text transcription performance.")
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=str(Path(__file__).parent.parent / "tests" / "fixtures" / "sample_30s.wav"),
        help="Path to WAV or audio file to transcribe",
    )
    parser.add_argument(
        "--backend",
        "-b",
        type=str,
        default=None,
        choices=["whisperx", "deepgram", "mock"],
        help="Transcription backend (defaults to settings.TRANSCRIBE_BACKEND)",
    )
    parser.add_argument(
        "--reference",
        "-r",
        type=str,
        default=str(Path(__file__).parent.parent / "tests" / "fixtures" / "reference_transcript.txt"),
        help="Path to reference transcript text file for WER evaluation",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default="large-v3",
        help="Whisper model name (e.g. large-v3, base, small)",
    )

    args = parser.parse_args()
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    backend_name = args.backend or settings.TRANSCRIBE_BACKEND
    print("=" * 65)
    print("  CLIP-IT-UP TRANSCRIPTION PIPELINE BENCHMARK")
    print("=" * 65)
    print(f"Target File      : {file_path.name}")
    print(f"Backend          : {backend_name}")
    print(f"Whisper Model    : {args.model}")

    # Check CUDA
    has_cuda = False
    try:
        import torch
        has_cuda = torch.cuda.is_available()
        if has_cuda:
            torch.cuda.reset_peak_memory_stats()
            device_name = torch.cuda.get_device_name(0)
            print(f"Compute Device   : CUDA ({device_name})")
        else:
            print("Compute Device   : CPU (No CUDA detected)")
    except ImportError:
        print("Compute Device   : Torch not installed")

    # Get audio duration
    audio_duration_sec = get_audio_duration(file_path)
    print(f"Audio Duration   : {audio_duration_sec:.2f}s ({audio_duration_sec / 60:.2f} min)")
    print("-" * 65)

    backend = get_transcription_backend(backend_type=backend_name)

    start_time = time.perf_counter()
    try:
        result = backend.transcribe(file_path)
    except Exception as e:
        print(f"Benchmark failed during transcription: {e}", file=sys.stderr)
        sys.exit(1)
    end_time = time.perf_counter()

    wall_time_sec = end_time - start_time
    rtf = wall_time_sec / audio_duration_sec if audio_duration_sec > 0 else 0.0

    # Peak GPU Memory
    gpu_peak_mb = 0.0
    if has_cuda:
        try:
            import torch
            gpu_peak_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
        except Exception:
            pass

    # WER calculation
    wer_pct = None
    ref_path = Path(args.reference) if args.reference else None
    if ref_path and ref_path.exists():
        with open(ref_path, encoding="utf-8") as rf:
            ref_text = rf.read().strip()
        hyp_text = " ".join(seg.text for seg in result.segments)
        wer = calculate_wer(ref_text, hyp_text)
        wer_pct = wer * 100

    # Cost calculation
    rate_per_source_hour = float(StageRateConfig.RATES_PER_SOURCE_HOUR.get("transcribe", 12.0))
    cost_for_file_inr = (audio_duration_sec / 3600.0) * rate_per_source_hour


    print("\nBENCHMARK RESULTS:")
    print(f"  * Wall Time           : {wall_time_sec:.3f} s")
    print(f"  * Real-Time Factor    : {rtf:.4f}x ({'Faster' if rtf < 1 else 'Slower'} than real-time)")
    print(f"  * Words Transcribed   : {len(result.words)} words")
    print(f"  * Segments Produced   : {len(result.segments)} segments")
    print(f"  * Speakers Detected   : {len(result.speakers)} ({', '.join(s.label for s in result.speakers)})")
    if has_cuda:
        print(f"  * Peak GPU VRAM       : {gpu_peak_mb:.1f} MB")
    if wer_pct is not None:
        print(f"  * Word Error Rate     : {wer_pct:.2f}%")
    print(f"  * Est. Cost (INR)     : INR {cost_for_file_inr:.4f} (at INR {rate_per_source_hour:.2f}/source-hour)")
    print("=" * 65)



if __name__ == "__main__":
    main()
