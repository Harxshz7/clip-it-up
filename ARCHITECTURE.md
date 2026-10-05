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

| Stage | Input | Output | Metric Recorded | Idempotency Rule |
| :--- | :--- | :--- | :--- | :--- |
| **`ingest`** | Uploaded video in S3 | Video metadata & checksum | `source_minutes` | Overwrite stage meta, upsert usage |
| **`proxy`** | Original video | 720p 30fps MP4 proxy | `cpu_seconds` | Replace proxy key, upsert usage |
| **`transcribe`**| Audio track | Word-level timed JSON | `audio_minutes` | Replace transcript JSON, upsert usage |
| **`candidates`**| Transcript & audio | Ranked clip candidates | `llm_tokens` | Upsert candidates by (job_id, index) |
| **`score`** | Candidate transcripts| Virality & retention score | `llm_tokens` | Upsert candidate scores |
| **`render`** | Proxy + crop coordinates| 1080x1920 MP4 vertical clip| `gpu_seconds` | Overwrite rendered output, upsert usage |

- **Idempotency Guarantee**: `job_stages` enforces `UNIQUE(job_id, name)` and `usage` enforces `UNIQUE(job_id, metric)` via PostgreSQL `ON CONFLICT DO UPDATE`.

---

## 3. Storage & Realtime Data Flow

- **Storage Key Convention**: `users/{user_id}/videos/{video_id}/source/{sanitized_filename}`.
- **Direct Upload Flow**:
  1. Frontend calls `POST /videos/upload-url` $\rightarrow$ API issues presigned PUT URL (or multipart URLs for $>100$ MB).
  2. Browser uploads directly to MinIO/S3 with byte-level progress.
  3. Frontend calls `POST /videos/{id}/complete` $\rightarrow$ API verifies object existence via S3 `HEAD`, creates `Job`, and dispatches worker.
- **Realtime SSE Flow**:
  1. Frontend opens `GET /jobs/{id}/events` passing Bearer token in headers.
  2. API pushes full job snapshot immediately $\rightarrow$ bridges into Redis channel `job:{id}` $\rightarrow$ streams updates $\rightarrow$ sends 15s heartbeats $\rightarrow$ terminates on `succeeded`/`failed`.

---

## 4. Architectural Decisions

1. **SSE over WebSockets**: Unidirectional server-to-client streaming is lighter, reconnects natively with `Last-Event-ID`, and avoids stateful WebSocket connection managers.
2. **Fetch-Based SSE Client**: Native `EventSource` cannot pass `Authorization: Bearer` headers; a fetch reader allows secure JWT handling and typed payload parsing.
3. **Direct-to-S3 Presigned Uploads**: Uploading directly to storage bypasses API memory and network bandwidth bottlenecks.
4. **Multipart Threshold at 100 MB**: Single PUT is fast for small clips; multipart provides 4x concurrency and part retries for files up to 5 GB.
5. **Clerk for Authentication**: Offloads password hashing, MFA, and OAuth; verified statelessly via cached JWKS in FastAPI.
6. **Task Idempotency via DB Upserts**: PostgreSQL unique constraints on `(job_id, metric)` prevent duplicate ₹ INR billing rows during task retries.
7. **WhisperX over Standard Whisper (Planned)**: Provides phoneme-level word timestamps required for precise subtitle animation.
8. **ASS Subtitles First (Planned)**: Native FFmpeg ASS subtitle rendering supports kinetic word-level pop-ups without expensive canvas video renders.
9. **Talking-Head / Podcast Focus for v1**: Constraining camera angles and active speaker detection to 1–2 speakers maximizes AI framing accuracy.
10. **`packages/shared` as Single Source of Truth**: Monorepo shared TypeScript types prevent frontend/backend schema divergence.
