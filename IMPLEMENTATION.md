# Implementation Roadmap & Phase Plan

> Multi-phase delivery plan and task breakdown for 2 developers shipping clip-it-up in parallel.

## 1. Goals & Scope

- **Goal**: Web application turning long videos into engaging 9:16 vertical clips.
- **v1 Scope**: Podcasts, interviews, and talking-head videos (1–2 visible speakers, clear audio).
- **Non-Goals (v1)**: Gaming streams, high-action multicam sports, complex multi-layer timeline editors, mobile native apps.

## 2. Team Split & Ownership

- **`<DEV_A>`**: Backend, media pipeline, AI/ML models, Celery tasks, infrastructure.
- **`<DEV_B>`**: Frontend, Next.js UI, clip player/editor, state management, SSE integration.
- **Boundary**: API contracts and TypeScript schemas in [`packages/shared/`](packages/shared).

---

## 3. Phase Delivery Table

| Phase | Weeks | Done-When | Status | Owner |
| :--- | :--- | :--- | :--- | :--- |
| **0. Foundation** | W1–2 | Presigned S3 upload, dummy 6-stage worker, live SSE progress, ₹ INR cost recording | **Complete** | `<DEV_A>` / `<DEV_B>` |
| **1. Transcript** | W3–4 | Real WhisperX audio extraction, word-level timestamps, speaker diarization, interactive viewer | **Complete** | `<DEV_A>` / `<DEV_B>` |
| **2. Clip Selection**| W5–8 | LLM virality scoring (Claude API), candidate hook extraction, ranking | Planned | `<DEV_A>` |
| **2.5 Reality Check**| W9 | Creators test raw AI clip cuts; validate hook retention against baseline | Planned | `<DEV_A>` / `<DEV_B>` |
| **3. Reframe** | W10–12| Face tracking + active speaker detection (9:16 auto-crop) via FFmpeg | Planned | `<DEV_A>` |
| **4. Captions & Export** | W13–14| ASS dynamic animated subtitles burned into exported 1080x1920 MP4 | Planned | `<DEV_A>` |
| **5. Clip Editor** | W15–16| Web UI trimming, caption styling, speaker switch overrides, instant preview | Planned | `<DEV_B>` |
| **6. Soft Launch** | W17–18| End-to-end user onboarding, Clerk billing gates, 50 creator beta | Planned | `<DEV_A>` / `<DEV_B>` |
| **7. Post-Launch** | W19+ | Batch uploads, custom font presets, multi-aspect export (1:1, 4:5) | Planned | `<DEV_A>` / `<DEV_B>` |

---

## 4. Phase Task Checklist

### Phase 1: Transcript Pipeline (Weeks 3–4) — COMPLETE
- [x] `[worker]` Replace dummy ingest with FFprobe validation, S3 download stream, and error codes (`NO_AUDIO`, `TOO_LONG`, `UNSUPPORTED_CODEC`, `CORRUPT_FILE`).
- [x] `[worker]` Replace dummy proxy with parallel FFmpeg execution producing 16kHz mono WAV and 720p H.264 preview proxy with pipe progress.
- [x] `[worker]` Implement WhisperX transcription backend with faster-whisper, wav2vec2 alignment, and pyannote diarization, plus Deepgram adapter and Mock engine.
- [x] `[worker]` Implement dual Celery worker queues (`cpu` and `gpu`), Dockerfile.cpu, Dockerfile.gpu, and docker compose profile `gpu`.
- [x] `[worker]` Build sentence segments from words, persist `raw.json` to S3, and commit transcript/words/segments/speakers to DB in one transaction.
- [x] `[worker]` Emit `transcript_ready` SSE event and `partial_results: { transcript: true }` so frontend renders transcript immediately.
- [x] `[api]` Add `GET /videos/{id}/transcript` (with `?from_ms&to_ms` range filtering).
- [x] `[api]` Add `GET /videos/{id}/transcript/words` (word-level time-range queries).
- [x] `[api]` Add `PATCH /videos/{id}/speakers/{speaker_id}` for inline speaker name editing.
- [x] `[api]` Add `GET /videos/{id}/proxy-url` for presigned 720p proxy video stream.
- [x] `[api]` Add `GET /videos/{id}/transcript/export?format=txt|srt|vtt|json`.
- [x] `[web]` Build side-by-side video player and transcript viewer with word-level seek, colored speaker labels, inline renaming, auto-scroll with manual pause, search highlighting & navigation, and multi-format exports.
- [x] `[eval]` Add `scripts/bench_transcribe.py`, `make bench`, and fixtures with reference transcript.

### Phase 2: AI Clip Discovery (Weeks 5–8)
- [ ] `[worker]` Prompt Claude 3.5 Sonnet to detect 30–90s coherent narrative arcs and hooks.
- [ ] `[worker]` Score virality (hook strength, pacing, payoff) and store candidate clips in DB.
- [ ] `[api]` Add `GET /videos/{id}/clips` endpoint with ranking metadata.
- [ ] `[web]` Build clip candidate card deck with confidence scores and hook previews.

### Phase 3 & 4: Reframe, Captions & Render (Weeks 10–14)
- [ ] `[worker]` Implement MediaPipe/YOLO face tracking for 1–2 speaker 9:16 auto-framing.
- [ ] `[worker]` Generate styled ASS subtitle files with word-level highlight animations.
- [ ] `[worker]` FFmpeg hardware-accelerated render pipeline writing final clips to S3.
- [ ] `[api]` Add presigned download URL generator for completed clips.

### Phase 5 & 6: Editor & Soft Launch (Weeks 15–18)
- [ ] `[web]` Build trim handles, caption text editor, and subtitle style picker.
- [ ] `[infra]` Deploy GPU worker pool on cloud provider with auto-scaling.
- [ ] `[api]` Hook Clerk webhooks for subscription limits and usage metering.

---

## 5. Known Gaps (Plan vs Actual Repo)

1. **Pipeline Execution**: Phase 1 stages (`ingest`, `proxy`, `transcribe`) are fully implemented and real. Stages 4–6 (`candidates`, `score`, `render`) remain simulated dummies until Phase 2/3/4.
2. **Clerk In Dev**: [`apps/api/src/api/dependencies.py`](apps/api/src/api/dependencies.py) supports `DEV_AUTH_BYPASS=true` for local runs without live Clerk keys.
3. **Evaluation Suite**: Phase 1 transcription benchmarking script is at [`scripts/bench_transcribe.py`](scripts/bench_transcribe.py); virality datasets are scheduled for Phase 2.
