"""Contact sheet visual inspection tool generating 12-frame grid PNGs with crop box overlays."""
import os
import cv2
import numpy as np
from clip_shared.schemas.reframe import ReframeCropPath, ReframeKeyframe


def generate_contact_sheet(
    video_path: str,
    crop_path: ReframeCropPath | dict,
    start_ms: int,
    end_ms: int,
    output_png_path: str,
    grid_cols: int = 4,
    grid_rows: int = 3,
    thumb_w: int = 320,
    thumb_h: int = 180,
) -> str:
    """
    Generate a 12-frame grid PNG displaying sampled frames with 9:16 crop boundaries.
    """
    os.makedirs(os.path.dirname(output_png_path), exist_ok=True)

    if isinstance(crop_path, dict):
        keyframes_data = crop_path.get("keyframes", [])
        keyframes = [ReframeKeyframe(**k) if isinstance(k, dict) else k for k in keyframes_data]
    else:
        keyframes = crop_path.keyframes

    num_frames = grid_cols * grid_rows
    duration_ms = max(100, end_ms - start_ms)
    sample_timestamps = [
        int(start_ms + (i / float(num_frames - 1)) * duration_ms)
        for i in range(num_frames)
    ]

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        # Generate dummy fallback contact sheet if video not openable
        blank = np.zeros((grid_rows * thumb_h, grid_cols * thumb_w, 3), dtype=np.uint8)
        cv2.putText(blank, "Video Not Available", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.imwrite(output_png_path, blank)
        return output_png_path

    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    thumbs: list[np.ndarray] = []

    for t_ms in sample_timestamps:
        frame_idx = int((t_ms / 1000.0) * src_fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret or frame is None:
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Find keyframe or interpolate
        active_kf = keyframes[0] if keyframes else ReframeKeyframe(t_ms=t_ms, cx=0.5, cy=0.5, w=0.3164, h=1.0)
        for kf in keyframes:
            if kf.t_ms <= t_ms:
                active_kf = kf

        h, w = frame.shape[:2]
        crop_x1 = int((active_kf.cx - (active_kf.w / 2.0)) * w)
        crop_x2 = int((active_kf.cx + (active_kf.w / 2.0)) * w)
        crop_y1 = int((active_kf.cy - (active_kf.h / 2.0)) * h)
        crop_y2 = int((active_kf.cy + (active_kf.h / 2.0)) * h)

        # Draw 9:16 crop rectangle on frame (Magenta / Indigo)
        cv2.rectangle(frame, (crop_x1, crop_y1), (crop_x2, crop_y2), (255, 0, 200), 3)

        # Draw timestamp label
        label = f"{(t_ms - start_ms) / 1000.0:.1f}s (cx={active_kf.cx:.2f})"
        cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        thumb = cv2.resize(frame, (thumb_w, thumb_h))
        thumbs.append(thumb)

    cap.release()

    # Stitch into grid
    rows = []
    for r in range(grid_rows):
        row_thumbs = thumbs[r * grid_cols:(r + 1) * grid_cols]
        rows.append(np.hstack(row_thumbs))
    sheet = np.vstack(rows)

    cv2.imwrite(output_png_path, sheet)
    return output_png_path
