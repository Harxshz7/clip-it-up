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
| **2. Clip Selection**| W5–8 | LLM virality scoring (Claude API), candidate hook extraction, ranking, streaming SSE, eval harness | **Complete** | `<DEV_A>` / `<DEV_B>` |
| **2.5 Reality Check**| W9 | Tooling for 5 creators to review raw AI cuts, download crude clips, exit survey & gate report | **Complete** | `<DEV_A>` / `<DEV_B>` |

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

### Phase 2: AI Clip Discovery & Evaluation (Weeks 5–8) — COMPLETE
- [x] `[worker]` Sliding sentence-boundary window generator (15–90s), hook and conclusion scoring heuristics.
- [x] `[worker]` Quality filters: topic coherence, filler ratio, silence threshold (>30%), and single-speaker dominance.
- [x] `[worker]` Acoustic feature extraction (RMS energy, spectral flux, pitch variance, laughter detector, pause map) stored to S3 as `.npz` and DB.
- [x] `[worker]` Two-pass LLM scoring (Claude 3.5 Sonnet + Haiku) with SHA-256 response caching and full video summary context.
- [x] `[worker]` Multi-modal signal combiner (hook, emotion, coherence, payoff, novelty, audio energy, laughter, penalties).
- [x] `[worker]` Overlap deduplication (IoU > 0.3) and temporal diversity filter (max 2 clips per 5-min window).
- [x] `[worker]` Sentence-boundary aligned multi-length variants (15s, 30s, 45s, 60s, auto).
- [x] `[worker]` Real-time SSE streaming (`clip_scored` events emitted per batch).
- [x] `[api]` Add `GET /videos/{id}/clips`, `GET /clips/{id}`, `POST /clips/{id}/feedback`, `POST /videos/{id}/rescore`, `GET /videos/{id}/scoring-runs`.
- [x] `[web]` Interactive ClipsDeck and ClipCard with score breakdown tooltips, variant selector, proxy video preview seek, and thumbs feedback.
- [x] `[web]` Blind human rater interface at `/eval/rate` for 3 independent raters with CSV export.
- [x] `[eval]` Eval harness with 10 benchmark videos, ground truth ratings, `make eval` (Precision@5, AUC, correlations, cost diffs), `make tune` (coordinate search), and `docs/eval.md`.

### Phase 2.5: Creator Reality Check (Week 9) — COMPLETE
- [x] `[db]` Alembic migration `0004_phase2_5_creator_review` (`review_sessions`, `review_ratings`, `review_survey`, `clip_review_exports`).
- [x] `[worker]` Lazy FFmpeg crude clip export task (horizontal + 9:16 center-crop + watermark overlay, safe argument lists, idempotent rerun).
- [x] `[api]` Added `POST /videos/{id}/review-sessions`, `GET /review/{token}` (unanchored score hiding, rate limited, constant-time compare), `PUT /review/{token}/ratings/{clip_id}`, `PUT /review/{token}/survey`, `POST /review/{token}/submit`, `DELETE /review-sessions/{id}`.
- [x] `[web]` Public mobile-first review flow at `/review/[token]` (crude disclaimers, video player with 9:16 / 16:9 toggle, 3 verdict buttons, reason chips, comment auto-save, exit survey, download crude clips).
- [x] `[web]` Owner review management at `/videos/[id]/reviews` (create session, list, copy link, detailed rating & survey inspect) and Gate Report viewer at `/reviews/gate`.
- [x] `[eval]` Gate decision report generator (`make gate`, `eval/gate.py`, `eval/run_gate.py`, `config/gate.yaml`, fixtures test suite, markdown + JSON output).
- [x] `[docs]` Created `docs/creator-check.md` with outreach templates, call scripts, question checklist, operational protocol, and results log.

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
