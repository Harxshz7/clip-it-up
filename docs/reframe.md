# 📐 Automatic 9:16 Reframing (Phase 3 & Phase 7b)

> High-performance, heuristic-driven 9:16 vertical reframing for social video clips (TikTok, Instagram Reels, YouTube Shorts), covering solo talking heads, 2-shots, multi-person panels, presentations, screen shares, and code walkthroughs.

---

## 1. Design Philosophy

Bad framing is the #1 reason creators abandon automated clip tools. The reframing engine adheres to core principles:
1. **Never cut an active speaker's face**: Active speaker face bounding boxes are clamped with $\ge 10\%$ safety padding and look-room.
2. **Never jitter or ping-pong**: Trajectories are smoothed via deadzones, velocity caps, and exponential moving averages. Speaker alternation faster than $1.5\text{s}$ triggers anti-ping-pong smoothing into balanced or split-screen framing.
3. **Keep screen text readable**: If text would scale below mobile readability limits ($< 14\text{px}$ effective font height on $1080\text{w}$ output), the planner flags `unreadable_text` and cleanly falls back to `content_fit`.
4. **Single render pipeline**: All layouts (`split_stack`, `stack`, `pip`, `content_fit`, `content_zoom`) compile into unified FFmpeg filter subgraphs consumed directly by the single EDL filtergraph builder. No second render path.
5. **Always degrade gracefully**: If visual tracking or speaker association confidence falls below threshold, the pipeline falls back along a deterministic chain.

---

## 2. Reframing Modes & Layouts

| Mode | Trigger Condition | Visual Layout & Behavior | Default Status |
| :--- | :--- | :--- | :--- |
| **`speaker_track`** | 1 visible speaker or clear active speaker in a group | Tight 9:16 crop centered on active speaker with look-room; switches on speaker turns with $\ge 1.5\text{s}$ minimum hold. | **Default** |
| **`balanced`** | 2 visible speakers fitting in 9:16 crop width | Centers between both speakers simultaneously without pan switching. | **Default** |
| **`split_stack`** | 2 or wide group speakers who cannot fit into a single 9:16 crop | Vertical stack of two $1080 \times 960$ half-screens framing active conversation participants. | **Default** |
| **`content_fit`** | Slides, webinars, dashboards with small text | Full $16:9$ source frame scaled to width, centered with blurred background. Never crops slide content. | **Default** |
| **`content_zoom`** | Screen recording or whiteboard with readable ROI | Smooth zoom into detected region of interest (code editor, active window), snapped to text line bounds. | **Default** |
| **`pip`** | Webinar or slide presentation with speaker thumbnail | Full presentation scaled with speaker thumbnail rendered as a rounded Picture-in-Picture overlay in a safe corner. | **Default** |
| **`stack`** | Presentation slides with prominent speaker video | Content on top ($60\%$), speaker video below ($40\%$). | **Default** |
| **`center`** | Static shots or fallback with no clear face tracks | Static center crop $(0.5, 0.5)$. | **Fallback** |
| **`fit_blur`** | General fallback for unclassifiable shots | Fits source scaled to width on blurred background. | **Fallback** |

---

## 3. Fallback Chain

When tracking or ROI uncertainty arises, the planner transitions along this chain:

```text
[ speaker_track ] ──(all fit)──> [ balanced ] ──(group/wide)──> [ split_stack ]
       │                                                                │
   (low conf)                                                       (low conf)
       ▼                                                                ▼
 [ largest_face ] ─────────────> [ center ] ─────────────> [ fit_blur / content_fit ]
```

For screen content:
```text
[ content_zoom ] ──(text < 14px or low conf)──> [ content_fit ] ──(error)──> [ fit_blur ]
[ pip ] ──(face thumbnail too small or lost)──> [ content_fit ] ──(error)──> [ fit_blur ]
```

Every fallback records an explicit `fallback_reason` (`screen_content_full_fit`, `unreadable_text_micro_font`, `pip_low_confidence_or_disabled`, `content_zoom_disabled`, `no_faces_detected`).

---

## 4. Multi-Person Framing Heuristics

### A. N-Track Hungarian Speaker Association
- Global assignment maps diarization speaker labels (`SPEAKER_00`, `SPEAKER_01`, ...) to face tracks using the Hungarian linear sum assignment algorithm on an affinity matrix combining speech-turn overlap and mouth motion variance correlation.
- Matrix is automatically padded to square dimensions for handling off-screen speakers and silent listener faces.

### B. Anti-Ping-Pong Cost Model
- Switches between speakers require a minimum hold time ($1500\text{ms}$).
- Fast back-and-forth speech triggers `ping_pong_prevented: true` in `flags`, preventing nauseating camera whip-pans by holding the current speaker or switching to `split_stack`.
- Distance threshold for hard cut vs smooth pan: camera pans if $\Delta x \le 0.35$; cuts cleanly if $\Delta x > 0.35$.

### C. Look-Room
- Speakers on the left side ($c_x < 0.5$) receive $+0.03$ rightward look-room; speakers on the right side receive $-0.03$ leftward look-room.

---

## 5. Screen-Content Framing Heuristics

### A. OCR-Lite Text Detection
- Fast morphological line clustering runs on sampled proxy frames in $< 5\text{ms}$.
- Detects bounding boxes for code lines, presentation headers, and dashboard blocks.

### B. Text Line Boundary Snapping
- ROI boxes are snapped to bounding text clusters with $4\%$ horizontal and vertical padding (`snap_roi_to_text_bounds`) so that text lines are never cut through.

### C. Mobile Readability Guard
- Computes effective font height:
  $$\text{effective\_font\_px} = \text{min\_font\_px} \times \left(\frac{1920}{\text{roi\_h} \times \text{src\_h}}\right)$$
- If $\text{effective\_font\_px} < 14.0\text{px}$, the planner flags `unreadable_text: true` and automatically drops back to `content_fit` to prevent unreadable blurry text on mobile screens.

### D. Corner Thumbnail Detector
- Identifies speaker PIP boxes in corner quadrants ($c_x < 0.28$ or $> 0.72$, $c_y < 0.28$ or $> 0.72$, area $< 0.045$).
- Promotes scenes to `hybrid_pip` and routes to `pip` layout.

---

## 6. Evaluation & QA Benchmarks

The benchmark suite evaluates 11 comprehensive scenarios covering all 7 scene types:
1. `talking_head_single_speaker` (Solo talking head)
2. `two_person_balanced` (2-person cozy dialogue)
3. `presentation_slides_fallback` (Open courseware slides)
4. `panel_4_person_tech` (4-person panel conference)
5. `group_podcast_wide` (Wide multi-person podcast)
6. `interview_cutaway_reaction` (Interview with reaction pauses)
7. `webinar_slides_thumbnail_pip` (Slide presentation with presenter PIP)
8. `screen_recording_code_demo` (VS Code demo)
9. `screen_recording_unreadable_tiny` (Micro-font analytics dashboard)
10. `whiteboard_lecture_roi` (Physics whiteboard equations)
11. `hybrid_speaker_then_slides` (Keynote intro transitioning to slides)

Run the evaluation suite:
```bash
python scripts/reframe_eval.py
# or
make reframe-eval
```

### Measured Quality Gates

| Metric | Target | Actual (Phase 7b) | Status |
| :--- | :--- | :--- | :--- |
| **Face Inside Crop Rate** | $\ge 99.0\%$ | **$100.0\%$** | ✅ PASS |
| **Ping-Pong Rate** | $\le 1.0\text{ / min}$ | **$0.56\text{ / min}$** | ✅ PASS |
| **Human OK Rate (Group)** | $\ge 85.0\%$ | **$100.0\%$** | ✅ PASS |
| **Human OK Rate (Screen Content)** | $\ge 85.0\%$ | **$100.0\%$** | ✅ PASS |
| **Classifier Macro-F1** | $\ge 0.850$ | **$1.000$** | ✅ PASS |
| **V1 Modes Regression** | $\le 1.0\%$ | **$0.00\%$** | ✅ PASS |

Visual inspection contact sheets are generated at `eval/reports/reframe/contact_sheets/{clip_id}.png`.

---

## 7. How to Register & Label New Eval Clips

Use `scripts/add_reframe_eval_video.py` to register new benchmark videos:

```bash
# Register a new eval clip
python scripts/add_reframe_eval_video.py add --slug my_clip --name "My Conference Panel" --scene-type group --duration-ms 30000

# Export labels template
python scripts/add_reframe_eval_video.py export-labels --format yaml

# Import human reviews
python scripts/add_reframe_eval_video.py import-labels eval/labels/reframe_labels.yaml
```

Label verdicts must be `ok` or `bad` with a failure reason (`face_cut`, `wrong_speaker`, `jitter`, `bad_zoom`, `wrong_mode`, `text_cut`, `unreadable`).

---

## 8. Mode Deployment Configuration

All new layouts are controlled by confidence thresholds and configuration flags in `worker/reframe/planner.py`:
- `enable_split_stack`: Default `True` (passed gate targets $\ge 85\%$).
- `enable_content_zoom`: Default `True` (enforced with readability guard).
- `enable_pip`: Default `True` (enforced with thumbnail confidence guard $\ge 0.70$).
- `enable_stack`: Default `True`.
- `enable_reaction_switching`: Default `False` (opt-in; awaiting user-customizable reaction sensitivities).
