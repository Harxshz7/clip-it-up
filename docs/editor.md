# Phase 5: Editor Experience & Clip Grid

## 1. Overview
The Clip-It-Up Phase 5 Editor is the primary surface where creator trust is won. It provides an instantaneous, non-destructive editing workflow with guaranteed parity between client-side proxy preview and server-side production exports.

### Core Guarantees
- **5-Minute Rule**: First-time creators go from upload to exported clip in $\le 5$ minutes of hands-on active time.
- **Progressive Editing**: Users can open, review, and edit initial scored clips while background pipelines (e.g. later stages, reframe analysis) continue processing.
- **Zero Lost Work**: Multi-tier persistence combining 800ms debounced autosave, 30s version collapse windows, optimistic concurrency conflict detection (`If-Match` / 409), IndexedDB/localStorage crash recovery, and a 200-step undo/redo stack.
- **Proxy Parity**: Real-time canvas/CSS 9:16 reframe and styled caption preview on 720p proxy video with zero server round trips for preview (<100ms latency).

---

## 2. Edit Document Schema (`clip_edit_doc`)
The single source of truth for all clip edits. Shared TypeScript definition in `@clip-it-up/shared` and Pydantic model in `clip_shared.schemas.editor`.

```json
{
  "clip_id": "string",
  "base_clip_id": "string",
  "version": 1,
  "range": {
    "start_ms": 1000,
    "end_ms": 31000
  },
  "removals": [
    {
      "id": "uuid-string",
      "start_ms": 4200,
      "end_ms": 5100,
      "kind": "filler",
      "text": "um",
      "enabled": true
    }
  ],
  "captions": {
    "words": [
      {
        "text": "Hello",
        "start_ms": 1000,
        "end_ms": 1500,
        "speaker": "SPEAKER_00",
        "emphasis": false
      }
    ],
    "style_key": "bold_stroke",
    "style_overrides": {
      "fontSize": 24,
      "color": "#ffffff"
    },
    "enabled": true
  },
  "reframe": {
    "mode_overrides": {
      "seg_0": "track"
    },
    "keyframes": []
  },
  "hook": {
    "text": "The secret to SaaS growth",
    "source": "auto",
    "start_ms": 1000
  },
  "preset_key": "tiktok_9_16",
  "cleanup_options": {
    "remove_fillers": true,
    "remove_silence": true,
    "silence_threshold_ms": 500
  }
}
```

### Invariant Rules
1. **Source Milliseconds**: All timestamps (`start_ms`, `end_ms`) are recorded in absolute source video milliseconds. Output-timeline mapping always flows through `EditDecisionList`.
2. **Non-overlapping Removals**: Removals inside `removals` are non-overlapping and sorted chronologically. Disabled removals (`enabled: false`) are preserved for instant undo.
3. **Immutability of Auto-Data**: Auto transcripts and auto reframes are never destroyed. They serve as base layers upon which edits are applied.

---

## 3. Concurrency & Autosave Model
- **Autosave Debouncing**: Debounced to 800ms after user interaction.
- **Window Collapse**: Autosave requests within a 30-second window update the current version row in-place rather than generating unbounded version history.
- **Explicit Checkpoints**: Explicit actions (e.g. `Cmd+S`, regenerating, swapping hooks) trigger `is_checkpoint = true`, incrementing the version and saving a named rollback point.
- **Optimistic Concurrency**: `PUT /clips/{id}/edit` requires the `If-Match: <version>` header. If the server has a newer version, it returns HTTP `409 Conflict` containing the server document. The UI displays an actionable conflict modal:
  - **Reload Server Version**: Discards local diverging changes and adopts latest server state.
  - **Overwrite**: Bumps version count and forces client version over server version.
- **Crash Recovery**: After unexpected tab crashes or offline disconnects, the client detects newer drafts in storage and prompts the user to restore before continuing.

---

## 4. Progressive Editing
- When a video is uploaded, clips stream onto `/videos/[id]/clips` via `clip_scored` SSE events.
- Opening an early clip while video processing is ongoing works immediately.
- If reframe analysis has not finished, the editor displays an amber progressive badge (`"Analyzing framing..."`) with safe center-crop fallback.
- When `reframe_ready` arrives over SSE, the view smoothly upgrades in-place without resetting user trim or caption edits.
- Rescore events show a non-blocking toast banner allowing the creator to compare or dismiss updates.

---

## 5. Keyboard Shortcuts
| Shortcut | Action |
|---|---|
| `Space` | Play / Pause playback |
| `J` / `L` | Seek backward 1s / Seek forward 1s |
| `K` | Pause |
| `ArrowLeft` / `ArrowRight` | Step backward / forward 1 frame (33ms) |
| `Shift + ArrowLeft` / `Right` | Jump backward / forward 1 second |
| `[` | Set trim start boundary at current playhead |
| `]` | Set trim end boundary at current playhead |
| `Cmd/Ctrl + Z` | Undo last edit action |
| `Cmd/Ctrl + Shift + Z` | Redo last undone action |
| `Cmd/Ctrl + S` | Save explicit checkpoint |

---

## 6. Known Preview vs. Export Parity Differences
| Feature | Client Preview (Proxy) | Export Render (FFmpeg) |
|---|---|---|
| Resolution | 720p low-res proxy stream | 1080p source asset render |
| Audio Transitions | Web Audio API 15ms linear volume dip | FFmpeg `acrossfade` / equal-power splice |
| Font Rendering | CSS Canvas text render (`@font-face`) | libass subtitle renderer with identical font metrics |
| Color Space | Browser sRGB transform | Rec.709 encoded MP4 |

---

## 7. Metrics & Instrumentation Definitions
Instrumentation events are batched via `POST /editor/events`:
- **Time to First Clip Visible**: Duration from upload trigger until first scored clip renders in the clip grid.
- **Time to First Edit Action**: Milliseconds from opening the editor until the creator performs their first action (word click, tab switch, trim drag).
- **Hands-on Active Time**: Total time spent actively interacting with the editor. Pauses or idle gaps exceeding 20 seconds are strictly excluded by the heuristic:
  $$\text{ActiveTime} = \sum_{\Delta t_i \le 20\text{s}} \Delta t_i$$
- **Time to First Export**: Duration from editor open to first click on "Export Clip".
- **Export Without Editing Rate**: Percentage of exported clips where `version === 1` and no manual removals were added. Reflects quality of AI defaults.
