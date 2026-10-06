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

- **Idempotency Guarantee**: `job_stages` enforces `UNIQUE(job_id, name)` and `usage` enforces `UNIQUE(job_id, metric)` via PostgreSQL `ON CONFLICT DO UPDATE`.
- **Partial Results & SSE**: As soon as `transcribe` completes, `transcript_ready` SSE event is emitted and `job.partial_results = {"transcript": true}` is updated so the frontend renders the transcript viewer immediately while subsequent stages continue in the background.

---

## 3. Worker Topology & Celery Queues

- **Dual Queues**:
  - `cpu`: Dedicated for `ingest`, `proxy`, `candidates`, `score`. Runs `worker-cpu` image with FFmpeg/ffprobe.
  - `gpu`: Dedicated for `transcribe` (WhisperX) and `render`. Runs `worker-gpu` image with CUDA 12.1 runtime, PyTorch, faster-whisper, and wav2vec2 alignment models.
- **Docker Compose GPU Profile**: The `gpu` service runs under Docker Compose profile `--profile gpu`, enabling seamless local CPU development with `TRANSCRIBE_BACKEND=mock` or `deepgram`.

---

## 4. Phase 1 Data Models

- **`videos`**: Added `duration_seconds`, `width`, `height`, `fps`, `has_audio`, `proxy_key`, `audio_key`.
- **`transcripts`**: `id`, `video_id` (unique), `language`, `status` (`running` | `ready` | `failed`), `model`, `backend`, `word_count`, `created_at`.
- **`transcript_words`**: `id`, `transcript_id`, `idx`, `word`, `start_ms`, `end_ms`, `speaker`, `confidence`. Indexed on `(transcript_id, idx)`.
- **`transcript_segments`**: `id`, `transcript_id`, `idx`, `start_ms`, `end_ms`, `speaker`, `text`. Formed by sentence punctuation, speaker transitions, and max length.
- **`speakers`**: `id`, `transcript_id`, `label` (`SPEAKER_00`), `display_name` (user-editable).
- **S3 Source of Truth**: Full unreduced WhisperX JSON is archived at `users/{user_id}/videos/{video_id}/transcript/raw.json`.

---

## 5. Storage & Realtime Data Flow

- **Storage Key Conventions**:
  - Original source: `users/{user_id}/videos/{video_id}/source/{filename}`
  - Extracted audio: `users/{user_id}/videos/{video_id}/audio/audio.wav`
  - Preview proxy: `users/{user_id}/videos/{video_id}/proxy/proxy_720p.mp4`
  - Raw transcript: `users/{user_id}/videos/{video_id}/transcript/raw.json`
- **Direct Upload Flow**:
  1. Frontend calls `POST /videos/upload-url` $\rightarrow$ API issues presigned PUT URL (or multipart URLs for $>100$ MB).
  2. Browser uploads directly to MinIO/S3 with byte-level progress.
  3. Frontend calls `POST /videos/{id}/complete` $\rightarrow$ API verifies object existence via S3 `HEAD`, creates `Job`, and dispatches worker.
- **Realtime SSE Flow**:
  1. Frontend opens `GET /jobs/{id}/events` passing Bearer token in headers.
  2. API pushes full job snapshot immediately $\rightarrow$ bridges into Redis channel `job:{id}` $\rightarrow$ streams updates $\rightarrow$ sends 15s heartbeats $\rightarrow$ terminates on `succeeded`/`failed`.

---

## 6. Architectural Decisions

1. **SSE over WebSockets**: Unidirectional server-to-client streaming is lighter, reconnects natively with `Last-Event-ID`, and avoids stateful WebSocket connection managers.
2. **Fetch-Based SSE Client**: Native `EventSource` cannot pass `Authorization: Bearer` headers; a fetch reader allows secure JWT handling and typed payload parsing.
3. **Direct-to-S3 Presigned Uploads**: Uploading directly to storage bypasses API memory and network bandwidth bottlenecks.
4. **Multipart Threshold at 100 MB**: Single PUT is fast for small clips; multipart provides 4x concurrency and part retries for files up to 5 GB.
5. **Clerk for Authentication**: Offloads password hashing, MFA, and OAuth; verified statelessly via cached JWKS in FastAPI.
6. **Task Idempotency via DB Upserts**: PostgreSQL unique constraints on `(job_id, metric)` prevent duplicate ₹ INR billing rows during task retries.
7. **WhisperX + Wav2Vec2 Alignment + Pyannote**: Provides phoneme-level word timestamps and speaker diarization required for sentence chunking and kinetic subtitles.
8. **Pluggable Transcribe Backends**: `whisperx` (full GPU pipeline), `deepgram` (thin cloud API adapter with identical output schema), and `mock` (fast deterministic CI/dev engine).
9. **Dual Worker Images & Compose Profiles**: Clean separation of CPU tasks (FFmpeg) from heavy CUDA dependencies.
10. **`packages/shared` as Single Source of Truth**: Monorepo shared TypeScript types prevent frontend/backend schema divergence.

