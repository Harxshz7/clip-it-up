"""Generate synthetic 30-second 16kHz mono WAV fixture for testing."""
import math
import struct
import wave
from pathlib import Path


def generate_test_wav(output_path: Path, duration_sec: int = 30, sample_rate: int = 16000):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = duration_sec * sample_rate

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        # Generate harmonic modulated tone simulating speech formant frequencies (440Hz + 880Hz)
        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            # 2Hz envelope modulation with 440Hz & 880Hz carriers
            envelope = 0.5 * (1 + math.sin(2 * math.pi * 2 * t))
            val = int(16000 * envelope * 0.7 * (math.sin(2 * math.pi * 440 * t) + 0.3 * math.sin(2 * math.pi * 880 * t)))
            clamped = max(-32768, min(32767, val))
            frames.extend(struct.pack("<h", clamped))

        wav_file.writeframes(frames)


if __name__ == "__main__":
    out = Path(__file__).parent / "sample_30s.wav"
    generate_test_wav(out)
    print(f"Generated test WAV fixture at {out}")
