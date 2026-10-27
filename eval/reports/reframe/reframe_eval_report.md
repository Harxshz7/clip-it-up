# 📐 Phase 7b Reframe Evaluation & Quality Gates Report

> Generated on 2026-10-26T05:10:16.502904+00:00

## Quality Gates Status: 🟢 PASS

| Quality Gate Metric | Actual | Target | Status |
| :--- | :--- | :--- | :--- |
| **`face_inside_crop`** | `1.0` | `>= 0.990` | ✅ PASS |
| **`ping_pong_rate`** | `0.56` | `<= 1.0 / min` | ✅ PASS |
| **`human_ok_group`** | `1.0` | `>= 0.850` | ✅ PASS |
| **`human_ok_screen_content`** | `1.0` | `>= 0.850` | ✅ PASS |
| **`v1_modes_regression`** | `0.0` | `<= 0.010` | ✅ PASS |
| **`classifier_macro_f1`** | `1.0` | `>= 0.850` | ✅ PASS |

## 1. Scene Classifier Evaluation

- **Overall Accuracy:** `100.0%`
- **Macro-F1 Score:** `1.000` (Target: `>= 0.850`)

### Per-Class Performance

| Class | Precision | Recall | F1 Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| `talking_head` | `1.00` | `1.00` | `1.00` | 2 |
| `two_shot` | `1.00` | `1.00` | `1.00` | 2 |
| `group` | `1.00` | `1.00` | `1.00` | 2 |
| `screen_content` | `1.00` | `1.00` | `1.00` | 4 |
| `whiteboard` | `1.00` | `1.00` | `1.00` | 1 |
| `hybrid_pip` | `1.00` | `1.00` | `1.00` | 1 |
| `b_roll_other` | `1.00` | `1.00` | `1.00` | 0 |

### Confusion Matrix

| True \ Pred | `talking_head` | `two_shot` | `group` | `screen_content` | `whiteboard` | `hybrid_pip` | `b_roll_other` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `talking_head` | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| `two_shot` | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| `group` | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| `screen_content` | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| `whiteboard` | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| `hybrid_pip` | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| `b_roll_other` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## 2. Per-Scene-Type Breakdown

| Scene Type | Clips | Human OK | Face Inside | Fallback Rate |
| :--- | :--- | :--- | :--- | :--- |
| `talking_head` | 1 | `100.0%` | `100.0%` | `0.0%` |
| `two_shot` | 2 | `100.0%` | `100.0%` | `0.0%` |
| `screen_content` | 4 | `100.0%` | `100.0%` | `50.0%` |
| `group` | 2 | `100.0%` | `100.0%` | `0.0%` |
| `hybrid_pip` | 1 | `100.0%` | `100.0%` | `0.0%` |
| `whiteboard` | 1 | `100.0%` | `100.0%` | `0.0%` |

## 3. Evaluated Clips & Baseline Diff

| Clip ID | Scene Type | Mode | Layout | Conf | Jitter | Face Inside | V1 Diff |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `talking_head_single_speaker` | `talking_head` | `speaker_track` | `crop` | `0.98` | `0.0` | `100.0%` | ΔFace: +0.00, ΔJit: +0.0000 |
| `two_person_balanced` | `two_shot` | `balanced` | `crop` | `0.94` | `0.0` | `100.0%` | ΔFace: +0.00, ΔJit: +0.0000 |
| `presentation_slides_fallback` | `screen_content` | `content_fit` | `content_fit` | `0.92` | `0.0` | `100.0%` | ΔFace: +0.00, ΔJit: +0.0000 |
| `panel_4_person_tech` | `group` | `speaker_track` | `crop` | `0.95` | `0.00628` | `100.0%` | N/A |
| `group_podcast_wide` | `group` | `split_stack` | `split_stack` | `0.93` | `0.0` | `100.0%` | N/A |
| `interview_cutaway_reaction` | `two_shot` | `speaker_track` | `crop` | `0.92` | `0.0` | `100.0%` | N/A |
| `webinar_slides_thumbnail_pip` | `hybrid_pip` | `pip` | `pip` | `0.94` | `0.0` | `100.0%` | N/A |
| `screen_recording_code_demo` | `screen_content` | `content_zoom` | `content_zoom` | `0.96` | `0.0` | `100.0%` | N/A |
| `screen_recording_unreadable_tiny` | `screen_content` | `content_fit` | `content_fit` | `0.93` | `0.0` | `100.0%` | N/A |
| `whiteboard_lecture_roi` | `whiteboard` | `content_zoom` | `content_zoom` | `0.91` | `0.0` | `100.0%` | N/A |
| `hybrid_speaker_then_slides` | `screen_content` | `speaker_track` | `crop` | `0.95` | `2e-05` | `100.0%` | N/A |
