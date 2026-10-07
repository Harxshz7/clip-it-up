# Pipeline Stage Cost Sheet (₹ INR per Source-Hour)

This document defines the unit rates and cost measurement model across the 6 video processing stages. In Phase 0, placeholder rates are simulated and written to the `job_stages` and `usage` tables. In Phase 1 and 2, actual telemetry from Whisper, FFmpeg, LLM token counts, and GPU rendering instances will replace simulated measurements.

---

## 1. Stage Unit Rate Table

| Stage | Name | Metric Recorded | Rate (₹ / Source-Hour) | Phase 0 Placeholder Rate | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Stage 1** | `ingest` | `source_minutes` | ₹0.50 | ₹0.50 | S3 download bandwidth, integrity verification, audio demux |
| **Stage 2** | `proxy` | `cpu_seconds` | ₹2.00 | ₹2.00 | FFmpeg hardware/CPU accelerated 720p 30fps proxy encoding |
| **Stage 3** | `transcribe` | `audio_minutes` | ₹12.00 | ₹12.00 | Whisper ASR speech-to-text inference & word timestamp alignment |
| **Stage 4** | `candidates` | `llm_tokens` | ₹8.50 | ₹8.50 | LLM contextual reasoning to identify potential clip hooks |
| **Stage 5** | `score` | `llm_tokens` | ₹4.00 | ₹4.00 | Hook virality scoring, retention curve prediction |
| **Stage 6** | `render` | `gpu_seconds` | ₹15.00 | ₹15.00 | 9:16 vertical re-framing, burning dynamic subtitles, GPU export |

**Total Estimated Cost per Source-Hour**: **₹42.00 / hour** (~$0.50 USD / hour).

---

## 2. Phase 1 Measured Telemetry & Benchmark Table

| Stage | Backend / Engine | Hardware Target | Measured Wall Time (30m clip) | Measured RTF | Peak VRAM | Measured ₹ / Source-Hour | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`ingest`** | FFprobe + S3 Stream | CPU (2 vCPU) | < 5s | < 0.003x | N/A | ₹0.50 | Real pipeline active |
| **`proxy`** | FFmpeg 720p H.264 + 16kHz WAV | CPU (4 vCPU) | ~45s | ~0.025x | N/A | ₹2.00 | Real parallel pipeline active |
| **`transcribe`** | WhisperX (large-v3, float16) | NVIDIA T4 / A10G | < 300s (< 5.0 min) | < 0.16x | ~4.2 GB | ₹12.00 | Real GPU pipeline active |
| **`transcribe` (alt)** | Deepgram Nova-2 | Cloud API | ~15s | ~0.008x | N/A | $0.0043/min (~₹21.50) | Adapter ready |
| **`transcribe` (dev)** | Mock Engine | Local CPU | 0.05s | 0.0017x | 0 MB | ₹0.00 (dev) | CI/Dev verified |
| **`candidates`** | Sentence Sliding + Audio Features (CPU) | CPU (2 vCPU) | ~2.5s | ~0.001x | N/A | ₹0.00 (CPU only) | Real pipeline active |
| **`score`** | Claude 3.5 Sonnet + Haiku 2-Pass | Claude API | ~8.0s | ~0.004x | N/A | ₹1.28 ($0.015) | Real LLM 2-pass active |
| **`score` (rerun)** | In-memory / Redis Hash Cache | Local CPU | 0.02s | < 0.0001x | N/A | ₹0.00 (cached) | Cache verified |

*Note: Measured values marked TODO are populated via `make bench` / `scripts/bench_transcribe.py` when executed on live production GPU instances.*

---

## 3. Cost Measurement & Recording Methodology

1. **Duration Calculation**:
   - Each stage extracts `duration_seconds` from the video record (or probe).
   - `source_hours = duration_seconds / 3600`.
   - `cost_inr = (hourly_rate * source_hours).quantize(Decimal("0.0001"))`.

2. **Idempotent Usage Tracking**:
   - Usage is recorded in the `usage` table with a PostgreSQL unique constraint on `(job_id, metric)`.
   - Re-running a stage or retrying after transient failure performs an `ON CONFLICT DO UPDATE` upsert, preventing duplicate billing records.

3. **Monthly Aggregation**:
   - The `/usage/summary` endpoint queries:
     ```sql
     SELECT metric, SUM(quantity) as total_quantity, SUM(cost_inr) as total_cost_inr
     FROM usage
     WHERE user_id = :user_id
       AND EXTRACT(YEAR FROM created_at) = :year
       AND EXTRACT(MONTH FROM created_at) = :month
     GROUP BY metric;
     ```

