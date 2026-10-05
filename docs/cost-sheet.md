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

## 2. Cost Measurement & Recording Methodology

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
