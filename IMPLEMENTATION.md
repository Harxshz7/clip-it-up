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
| **3 & 4. Reframe/Captions/Export**| W10–14 | MediaPipe/YOLO reframe, 3 caption style packs, cleanup (fillers/silence), EDL & export presets | **Complete** | `<DEV_A>` / `<DEV_B>` |
| **5. Editor & Grid**| W15–16 | Single source-of-truth edit doc, 9:16 canvas preview, transcript trim/edit, inspector tabs, autosave/409, streaming grid | **Complete** | `<DEV_A>` / `<DEV_B>` |
| **6. Billing & Quotas**| W17–18 | Razorpay & Stripe dual gateways, dynamic quotas from `config/plans.yaml`, meter ledger, GST invoices | **Complete** | `<DEV_A>` / `<DEV_B>` |
| **7a. Brand Kit & Auto-Variants**| W19–20 | Custom logos/fonts/bumpers, single-pass render concat, 9:16 safe-zones, combinatoric A/B auto-variants, ZIP download | **Complete** | `<DEV_A>` / `<DEV_B>` |

---

## 4. Phase Task Checklist

### Phase 7a: Brand Kit & Auto-Variants (Weeks 19–20) — COMPLETE
- [x] `[db]` Alembic migration `0009_phase7a_brand_and_variants` (`brand_kits`, `brand_assets`, `variant_sets`, `clip_variants`, `exports.variant_id` with bidirectional relation fix and circular cascade protection).
- [x] `[shared]` Pydantic schemas in `clip_shared.schemas.brand` and `clip_shared.schemas.variants`, plus TypeScript interfaces in `@clip-it-up/shared`.
- [x] `[shared]` Asset validator in `clip_shared.media.brand_validator` supporting logo dimension/format check (Pillow), TTF/OTF font tables (fontTools), and video bumpers (ffprobe).
- [x] `[shared]` Render filtergraph in `clip_shared.media.render` supporting 9:16 safe-zone logo overlay, intro/outro video+audio concat with silence padding and acrossfades, and composite loudnorm.
- [x] `[worker]` Celery tasks `validate_brand_asset_task` and updated `render_export_task` with brand asset download, watermark enforcement, and temp cleanup.
- [x] `[api]` Brand Kit REST API: `/brand-kits` CRUD, `/brand-kits/default`, `/brand-assets` presigned upload, server-side plan gating.
- [x] `[api]` Auto-variants generator: combinatorics across `{hook, caption_style, cta}` with baseline Variant A preservation, deduplication, LLM prompt caching, and cost tracking (₹0.15 / set).
- [x] `[api]` Variants REST API: `/clips/{id}/variants`, `/variant-sets/{id}/export`, `/variant-sets/{id}/download-zip` with `manifest.csv`, `/exports/{id}/metrics`.
- [x] `[api]` Account purge in `supervisor.purge_account_data_task` cascading brand asset S3 deletions and relational rows.
- [x] `[web]` Brand Settings page `/settings/brand` with interactive 9:16 safe-zone preview canvas, WCAG 2.1 color contrast check, and font license modal.
- [x] `[web]` Variants Inspector Tab `VariantsTab.tsx` with combinatoric generator controls, variant preview cards, batch export, and ZIP download.
- [x] `[web]` Brand toggles integrated into `CaptionsTab.tsx` and `ExportTab.tsx`.
- [x] `[test]` Test coverage: DB models, migrations, brand API, variants generator, variants API, single-pass render filtergraph, and frontend unit/Playwright specs.

### Phase 5: Editor Experience & Clip Grid (Weeks 15–16) — COMPLETE
- [x] `[db]` Alembic migration `0007_phase5_editor` (`clip_edits`, `clip_alternatives`, `editor_events`).
- [x] `[shared]` Single source of truth `clip_edit_doc` shared TS types in `@clip-it-up/shared` and Pydantic schemas in `clip_shared.schemas.editor`.
- [x] `[shared]` Deterministic `EditDecisionList` TypeScript class with full test parity against Python implementation.
- [x] `[api]` Edit state API: `GET/PUT /clips/{id}/edit` with `If-Match` optimistic concurrency & 30s autosave collapse window, checkpoints, restore, and reset.
- [x] `[api]` Alternatives & regenerate: `GET /clips/{id}/alternatives`, `POST /clips/{id}/regenerate` (creates non-destructive alternatives, records usage and cost_inr ₹0.15, emits SSE).
- [x] `[api]` Bulk actions `POST /clips/bulk` (dismiss/export) and batched telemetry `POST /editor/events`.
- [x] `[api]` Metrics admin endpoint `GET /admin/editor-metrics` computing active hands-on time, edit distributions, and drop-offs.
- [x] `[web]` 3-column studio layout at `/videos/[id]/clips/[clipId]/edit` (transcript, 9:16 proxy preview + transport, inspector tabs, bottom EDL strip).
- [x] `[web]` Real-time 720p proxy preview with canvas/CSS 9:16 transform, styled captions, safe-zone guides, and time-map skip playback.
- [x] `[web]` Transcript editing: word seek, drag-to-delete, trim handles, strike-through chips with undo, typo text editing.
- [x] `[web]` Inspector tabs: Captions (3 style packs, overrides), Framing (reframe modes, crop box, keyframes), Clean-up (fillers/silence toggles, saved seconds), Hook (alt hooks, why chosen), Export (presets, download, history).
- [x] `[web]` Clip grid `/videos/[id]/clips`: streaming SSE updates, stable ordering, bulk select toolbar, progressive reframe status badge.
- [x] `[web]` Resilience: 200-op undo/redo, 800ms debounced autosave, 409 conflict dialog, IndexedDB/local draft crash recovery.
- [x] `[eval]` Playwright speed-run E2E test verifying $\le 12$ action path, edit persistence, conflict handling, and parity vectors.

---

## 5. Known Gaps (Plan vs Actual Repo)

1. **Pipeline Execution**: Phase 1 stages (`ingest`, `proxy`, `transcribe`) are fully implemented and real. Stages 4–6 (`candidates`, `score`, `render`) remain simulated dummies until Phase 2/3/4.
2. **Clerk In Dev**: [`apps/api/src/api/dependencies.py`](apps/api/src/api/dependencies.py) supports `DEV_AUTH_BYPASS=true` for local runs without live Clerk keys.
3. **Evaluation Suite**: Phase 1 transcription benchmarking script is at [`scripts/bench_transcribe.py`](scripts/bench_transcribe.py); virality datasets are scheduled for Phase 2.
