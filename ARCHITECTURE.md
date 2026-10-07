# System Architecture & Technical Decisions

> System topology, data flow, pipeline execution model, and core architectural decisions for clip-it-up.

## 1. System Topology

```text
               +-------------------------------------------------------------+
               |                     Next.js 14 Web UI                       |
               |      - Direct S3/MinIO upload with part progress & retry    |
               |      - Realtime SSE stream with Last-Event-ID reconnect     |
               +-------------+-------------------------------+---------------+
                             |                               |
                   Presigned | PUT                 SSE Stream| & API Calls
                             v                               v
               +-------------+-------------+   +-------------+---------------+
               |     MinIO / S3 / R2       |   |         FastAPI API         |
               |   - Presigned single PUT  |   |  - Clerk JWKS / Dev Bypass  |
               |   - Multipart (parts/comp)|   |  - Presigned URL generation |
               |   - Storage key isolation |   |  - Ownership isolation      |
               +-------------+-------------+   +------+--------------+-------+
                             ^                        |              |
                    HEAD /   | Read Video             | Enqueue      | Job State
                    Download |                        v              v
               +-------------+-------------+   +------+-------+ +----+-------+
               |       Celery Worker       |<--| Redis Queue  | | PostgreSQL |
               |  - 6 Idempotent stages    |   |  & Pub/Sub   | | - users    |
               |  - Simulation & progress  |   +------+-------+ | - videos   |
               |  - ₹ INR cost recording   |          ^         | - jobs     |
               |  - Upserted usage rows    |----------+         | - stages   |
               +---------------------------+  Publish Events    | - usage    |
                                                                +------------+
```

---

## 2. Pipeline Execution & Idempotency

The Celery worker executes 6 sequential stages. Re-running any stage is strictly safe.

| Stage | Queue | Input | Output | Metric Recorded | Idempotency Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`ingest`** | `cpu` | Uploaded video in S3 | Video metadata, duration & probe | `source_minutes` | Overwrite stage meta, upsert usage |
| **`proxy`** | `cpu` | Original video | 720p H.264 proxy + 16kHz mono WAV | `cpu_seconds` | Parallel FFmpeg, replace proxy & audio keys |
| **`transcribe`**| `gpu` | 16kHz mono WAV | Timed words, segments, speakers, raw.json | `audio_minutes` | Replace transcript & DB rows, upsert usage |
| **`candidates`**| `cpu` | Transcript & audio | Ranked clip candidates | `llm_tokens` | Upsert candidates by (job_id, index) |
| **`score`** | `cpu` | Candidate transcripts| Virality & retention score | `llm_tokens` | Upsert candidate scores |
| **`render`** | `gpu` | Proxy + crop coordinates| 1080x1920 MP4 vertical clip| `gpu_seconds` | Overwrite rendered output, upsert usage |

- **Partial Results & SSE**:
  - As soon as `transcribe` completes, `transcript_ready` SSE event is emitted and `job.partial_results = {"transcript": true}` is updated so the frontend renders the transcript viewer immediately.
  - As `score` executes, progressive `clip_scored` SSE events are streamed as each candidate finishes, displaying cards one by one in the UI while the job is still running.

---

## 3. Worker Topology & Celery Queues

- **Dual Queues**:
  - `cpu`: Dedicated for `ingest`, `proxy`, `candidates`, `score`. Runs `worker-cpu` image with FFmpeg/ffprobe, librosa, and LLM structured scoring.
  - `gpu`: Dedicated for `transcribe` (WhisperX) and `render`. Runs `worker-gpu` image with CUDA 12.1 runtime, PyTorch, faster-whisper, and wav2vec2 alignment models.
- **Docker Compose GPU Profile**: The `gpu` service runs under Docker Compose profile `--profile gpu`, enabling seamless local CPU development with `TRANSCRIBE_BACKEND=mock` or `deepgram`.

---

## 4. Phase 1 & 2 Data Models

- **`videos`**: Added `duration_seconds`, `width`, `height`, `fps`, `has_audio`, `proxy_key`, `audio_key`.
- **`transcripts`**: `id`, `video_id` (unique), `language`, `status` (`running` | `ready` | `failed`), `model`, `backend`, `word_count`, `created_at`.
- **`transcript_words`**: `id`, `transcript_id`, `idx`, `word`, `start_ms`, `end_ms`, `speaker`, `confidence`. Indexed on `(transcript_id, idx)`.
- **`transcript_segments`**: `id`, `transcript_id`, `idx`, `start_ms`, `end_ms`, `speaker`, `text`.
- **`speakers`**: `id`, `transcript_id`, `label` (`SPEAKER_00`), `display_name` (user-editable).
- **`clip_moments`**: `id`, `video_id`, `transcript_id`, `start_ms`, `end_ms`, `rank`, `final_score`, `status` (`candidate` | `scored` | `selected` | `rejected`).
- **`scoring_runs`**: `id`, `video_id`, `prompt_version`, `scorer_version`, `weights`, `model`, `input_tokens`, `output_tokens`, `cost_inr`.
- **`clips`**: `id`, `moment_id`, `video_id`, `scoring_run_id`, `variant_length_s` (`15` | `30` | `45` | `60` | `auto`), `start_ms`, `end_ms`, `hook_text`, `title`, `final_score`, `score_breakdown`, `reason`, `model`.
- **`clip_feedback`**: `id`, `clip_id`, `user_id`, `value` (`up` | `down`), `reason_tag`.
- **`audio_features`**: `id`, `video_id`, `version`, `frames_key`, `summary` (RMS energy, spectral flux, pitch variance, laughter probability, pause map).
- **`eval_videos`** and **`eval_clip_ratings`**: Tracking benchmark ground-truth ratings.

---

## 5. Phase 2 Scoring Architecture

1. **Two-Pass LLM Scoring**:
   - **Pass 1 (Cheap / Coarse)**: Batched scoring evaluating coarse virality (1–10) on all candidates. Retains top ~40%.
   - **Pass 2 (Deep Structured)**: Per-candidate structured scoring of hook, emotion, coherence, payoff, and novelty (0–1), plus fine boundary trims and flags.
2. **Deterministic Response Caching**: Responses are cached by SHA-256 hash of `(prompt_version, model, candidate_text)`. Rescoring with weight changes costs 0 tokens.
3. **Multi-Modal Signal Combination**:
   $$\text{Final Score} = \sum w_i \cdot s_i + w_{\text{energy}} \cdot \text{Energy} + w_{\text{laughter}} \cdot \text{Laughter} - w_{\text{pause}} \cdot \text{PauseRatio} - w_{\text{flag}} \cdot \text{Flags}$$
4. **Diversity & Overlap Deduplication**: Suppresses overlapping moments ($\text{IoU} > 0.30$) and limits density to 2 clips per 5-minute window.
5. **Multi-Length Variants**: Generates 15s, 30s, 45s, 60s, and auto cuts aligned to sentence boundaries.

