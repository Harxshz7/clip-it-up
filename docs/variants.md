# Auto-Variants & Multi-Variant Export Architecture (Phase 7a)

## 1. Overview & Problem Statement

Short-form video performance heavily depends on the initial hook (first 3 seconds), caption visual pacing, and clear calls-to-action (CTA). Producing multiple variations manually is tedious and time-consuming. 

The **Auto-Variants Subsystem** in Phase 7a automates this workflow by generating structured, high-probability A/B test variations across 3 orthogonal dimensions:
1. **Hook**: Headline angle, curiosity gap, controversial assertion, direct question.
2. **Caption Style**: Kinetic subtitle style pack (`bold_pop`, `karaoke`, `cinematic`, `minimal`, `neon`).
3. **Call to Action (CTA)**: Channel-specific ending CTA (`follow`, `comment`, `share`, `save`, `link`).

---

## 2. Generator Engine (`clip_shared.variants.generator`)

### 2.1 Combinatorics & Variant A Invariant
The generator takes the existing base clip Edit Document as the baseline anchor:
- **Variant A**: Always represents the current user edit state unmodified (`Variant A (Baseline)`).
- **Candidates (B, C, D...)**: Derived through combinatoric substitution across the selected variation dimensions.
- **Deduplication**: Enforced via a tuple hash `(hook_text, caption_style_key, cta_text)`. Any variation identical to an existing variant is pruned.
- **Quota Clamping**: Clamped to the plan limit defined in `config/plans.yaml` (Free: 0, Creator: 4, Pro: 8).

### 2.2 LLM Reasoning & Caching
- **Prompt Architecture**: Structured JSON prompt (`clip_shared.prompts.variants_v1`) sent to Claude 3.5 Haiku. It receives clip transcript context, original hook, and target marketing goal.
- **Token Efficiency**: ~450 input tokens, ~300 output tokens (~₹0.15 / set).
- **Idempotency Hash**: A SHA256 checksum of `clip_id + prompt_version + dimensions` guarantees that re-triggering generation with identical settings yields cached results without incurring redundant LLM cost.

---

## 3. Data Model & REST API

### 3.1 Relational Schema
- **`VariantSet`**:
  - `id`: UUID (Primary Key).
  - `clip_id`: UUID (Foreign Key to `clips.id`, cascaded).
  - `user_id`: UUID (Foreign Key to `users.id`, indexed).
  - `dimensions`: JSONB (active variation dimensions).
  - `created_at`: Timestamp UTC.
- **`ClipVariant`**:
  - `id`: UUID (Primary Key).
  - `variant_set_id`: UUID (Foreign Key to `variant_sets.id`, cascaded).
  - `label`: string (`Variant A (Baseline)`, `Variant B`, etc.).
  - `hook_text`: string.
  - `caption_style_key`: string.
  - `cta_text`: string.
  - `edit_doc_override`: JSONB (complete fork of the `EditDoc` ready for immediate independent rendering).
  - `diff_summary`: JSONB (human-readable differences for UI badges).

### 3.2 Endpoints
- `POST /clips/{clip_id}/variants`: Generate a new variant set with candidate forks.
- `GET /clips/{clip_id}/variants`: Fetch existing variants and export statuses for a clip.
- `DELETE /variants/{variant_id}`: Remove a single variant.
- `POST /variant-sets/{variant_set_id}/export`: Queue batch rendering of selected variants.
- `GET /variant-sets/{variant_set_id}/download-zip`: Download completed MP4 exports packaged in a ZIP archive with `manifest.csv`.
- `PATCH /exports/{export_id}/metrics`: Track real-world post performance (views, likes, watch time %).

---

## 4. Packaging & Export Delivery

When downloading a batch of rendered variants via `GET /variant-sets/{id}/download-zip`:
1. S3 streams for each variant MP4 are fetched concurrently.
2. In-memory `zipfile.ZipFile` is constructed with `ZIP_DEFLATED`.
3. A standardized `manifest.csv` is embedded at the root of the ZIP archive:
   ```csv
   variant_id,label,hook,caption_style,cta,filename,resolution,duration_s,created_at
   ```
4. Creators can drag-and-drop the unzipped folder straight into scheduling tools (Buffer, Hootsuite, Later) or native platform uploaders with full tracking context.
