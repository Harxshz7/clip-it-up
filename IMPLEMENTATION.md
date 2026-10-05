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
| **1. Transcript** | W3–4 | Real WhisperX audio extraction, word-level timestamps, speaker diarization | Planned | `<DEV_A>` |
| **2. Clip Selection**| W5–8 | LLM virality scoring (Claude API), candidate hook extraction, ranking | Planned | `<DEV_A>` |
| **2.5 Reality Check**| W9 | Creators test raw AI clip cuts; validate hook retention against baseline | Planned | `<DEV_A>` / `<DEV_B>` |
| **3. Reframe** | W10–12| Face tracking + active speaker detection (9:16 auto-crop) via FFmpeg | Planned | `<DEV_A>` |
| **4. Captions & Export** | W13–14| ASS dynamic animated subtitles burned into exported 1080x1920 MP4 | Planned | `<DEV_A>` |
| **5. Clip Editor** | W15–16| Web UI trimming, caption styling, speaker switch overrides, instant preview | Planned | `<DEV_B>` |
| **6. Soft Launch** | W17–18| End-to-end user onboarding, Clerk billing gates, 50 creator beta | Planned | `<DEV_A>` / `<DEV_B>` |
| **7. Post-Launch** | W19+ | Batch uploads, custom font presets, multi-aspect export (1:1, 4:5) | Planned | `<DEV_A>` / `<DEV_B>` |

---

## 4. Phase Task Checklist

### Phase 1: Transcript Pipeline (Weeks 3–4)
- [ ] `[worker]` Replace dummy ingest with FFmpeg 16kHz mono audio extraction.
- [ ] `[worker]` Integrate WhisperX container for word-level timestamps and diarization.
- [ ] `[api]` Add `GET /videos/{id}/transcript` endpoint returning timed word blocks.
- [ ] `[web]` Build transcript review viewer with interactive word seeking.

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

1. **Pipeline Execution**: Stages in [`apps/worker/src/worker/tasks/pipeline.py`](apps/worker/src/worker/tasks/pipeline.py) currently simulate delay; WhisperX, Claude API, and FFmpeg face tracking are marked **Planned**.
2. **Clerk In Dev**: [`apps/api/src/api/dependencies.py`](apps/api/src/api/dependencies.py) supports `DEV_AUTH_BYPASS=true` for local runs without live Clerk keys.
3. **Evaluation Suite**: [`eval/README.md`](eval/README.md) is a placeholder for Phase 2 virality datasets.
