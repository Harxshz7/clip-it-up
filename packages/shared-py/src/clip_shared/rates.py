"""Cost and rate definitions for pipeline stages.
Rates are defined in Indian Rupees (INR - ₹) per source-hour of video.
"""
from decimal import Decimal


class StageRateConfig:
    """Config table of per-stage ₹ per source-hour rates."""

    # Placeholder rates in INR (₹) per source-hour
    RATES_PER_SOURCE_HOUR: dict[str, Decimal] = {
        "ingest": Decimal("0.50"),       # ₹0.50 / hr (S3 download, validation, metadata extraction)
        "proxy": Decimal("2.00"),        # ₹2.00 / hr (FFmpeg fast proxy generation)
        "transcribe": Decimal("12.00"),   # ₹12.00 / hr (Whisper ASR inference)
        "candidates": Decimal("8.50"),   # ₹8.50 / hr (LLM context analysis & clip proposal)
        "score": Decimal("4.00"),        # ₹4.00 / hr (Virality / hook scoring model)
        "analysis": Decimal("3.50"),     # ₹3.50 / hr (Video analysis, face tracking & scene detection)
        "render": Decimal("15.00"),      # ₹15.00 / hr (GPU video encoding, cropping, burning subtitles)
    }

    # Primary metric tracked per stage
    STAGE_METRICS: dict[str, str] = {
        "ingest": "source_minutes",
        "proxy": "cpu_seconds",
        "transcribe": "audio_minutes",
        "candidates": "llm_tokens",
        "score": "llm_tokens",
        "analysis": "cpu_seconds",
        "render": "gpu_seconds",
    }

    @classmethod
    def calculate_stage_cost(cls, stage_name: str, duration_seconds: float = 600.0) -> Decimal:
        """
        Calculate INR cost for a stage based on video duration in seconds.
        Default to 600s (10 min) if duration is not yet extracted in dummy stage.
        """
        hourly_rate = cls.RATES_PER_SOURCE_HOUR.get(stage_name, Decimal("1.00"))
        source_hours = Decimal(str(duration_seconds)) / Decimal("3600")
        # Round to 4 decimal places for precision
        cost = (hourly_rate * source_hours).quantize(Decimal("0.0001"))
        return cost

    @classmethod
    def get_stage_metric(cls, stage_name: str) -> str:
        return cls.STAGE_METRICS.get(stage_name, "source_minutes")

    @classmethod
    def calculate_metric_quantity(cls, stage_name: str, duration_seconds: float = 600.0) -> Decimal:
        """Simulate metric quantity produced for a given stage."""
        if stage_name in ("ingest", "proxy", "transcribe"):
            # in minutes
            return (Decimal(str(duration_seconds)) / Decimal("60")).quantize(Decimal("0.01"))
        elif stage_name in ("candidates", "score"):
            # in tokens (e.g. ~1500 tokens per minute of video)
            return (Decimal(str(duration_seconds)) * Decimal("25")).quantize(Decimal("1"))
        elif stage_name == "render":
            # in gpu seconds
            return Decimal(str(duration_seconds)).quantize(Decimal("0.01"))
        return Decimal("1.00")
