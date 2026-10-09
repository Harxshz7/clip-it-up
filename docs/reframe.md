# 📐 Automatic 9:16 Reframing (Phase 3)

> High-performance, heuristic-driven 9:16 reframing for vertical social video clips (TikTok, Instagram Reels, YouTube Shorts).

---

## 1. Design Philosophy

Bad framing is the #1 reason creators abandon automated clip tools. Phase 3 adheres to three foundational rules:
1. **Never cut a face**: Face bounding boxes are strictly clamped inside crop margins with $\ge 10\%$ safety padding.
2. **Never jitter**: Trajectories are smoothed via deadzones, velocity caps, and exponential moving averages; motion snaps cleanly across scene cuts without unnatural interpolation.
3. **Always degrade gracefully**: If visual tracking or speaker association confidence falls below threshold, the pipeline falls back along a deterministic chain to `fit_blur`.

---

## 2. Reframing Modes

| Mode | Trigger Condition | Visual Behavior |
| :--- | :--- | :--- |
| **`speaker_track`** | 1 visible speaker or clear active speaker | Centers horizontally on the speaker's face; places eyeline at upper third ($y \approx 0.33$), reserving bottom $20\%$ for subtitles/captions. |
| **`balanced`** | 2 visible speakers within $9:16$ crop width | Centers between both speakers simultaneously without pan switching. |
| **`center`** | No clear face tracks or static wide shot | Centers crop on frame midpoint $(0.5, 0.5)$. |
| **`fit_blur`** | Screen shares, slides, code editors, or $3+$ faces | Fits the full $16:9$ source frame scaled to width, overlaid on a blurred zoomed background. Never crops slides with text. |

---

## 3. Fallback Chain

When tracking uncertainty arises, the planner transitions along this chain:

```text
[ speaker_track ] ──(2 faces fit)──> [ balanced ] ──(faces too wide)──> [ speaker switch ] ──(uncertain)──> [ center ] ──(slides / risk)──> [ fit_blur ]
```

Every fallback records an explicit `fallback_reason` (`screen_share_detected`, `wide_multi_faces`, `low_confidence`, `face_cut_risk`).

---

## 4. Platform Safe Zones

Social video platforms superimpose profile icons, caption bars, and action buttons over vertical clips. Phase 3 maintains normalized safe margins:
- **Top Safe Zone ($12\%$)**: Profile name, live badges, audio tickers.
- **Bottom Caption Zone ($22\%$)**: Subtitle placement area (reserved for Phase 4 captions).
- **Right Action Column ($15\%$ on bottom right)**: Like, comment, share buttons.

---

## 5. Evaluation & QA Metrics

Run the evaluation suite via:
```bash
python scripts/reframe_eval.py
# or
make reframe-eval
```

### Measured Quality Gates

| Metric | Target | Description |
| :--- | :--- | :--- |
| **Face Inside Crop Rate** | $\ge 99.0\%$ | Percentage of sampled video frames where face is fully inside crop. |
| **Mean Jitter Score** | $< 0.005$ | Mean absolute second derivative of crop center ($\text{px/frame}^2$). |
| **Human OK Rate** | $\ge 90.0\%$ | Reviewer approval rate across labeled benchmark clips. |
| **Pan Speed 95th Pct** | $< 0.45\text{ units/s}$ | Prevents jarring camera motion. |

---

## 6. Manual Nudges & Persistence Model

- **Non-destructive manual overrides**: When a user drags the crop box in the UI, an edit record is inserted into `clip_reframe_edits`.
- **Auto preservation**: The auto-generated `clip_reframes` row remains untouched.
- **Revert**: Clicking "Reset to Auto" simply deletes the manual edit rows, restoring the auto-planned framing instantly.
