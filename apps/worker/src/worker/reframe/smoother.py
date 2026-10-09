"""Crop trajectory smoothing with deadzone, velocity clamping, hard cut snapping, and boundary constraints."""
from dataclasses import dataclass
import numpy as np
from clip_shared.schemas.reframe import ReframeKeyframe


@dataclass
class SmootherConfig:
    deadzone_x: float = 0.018  # ignore micro movements < 1.8% of frame
    deadzone_y: float = 0.018
    ema_alpha: float = 0.18  # smoothing factor (0.0 to 1.0)
    max_pan_speed_per_sec: float = 0.45  # maximum normalized screen width per second
    safe_margin: float = 0.04  # margin around face


class CropSmoother:
    """Smooths crop centers and enforces safe bounding box constraints."""

    def __init__(self, config: SmootherConfig | None = None):
        self.cfg = config or SmootherConfig()

    def smooth_trajectory(
        self,
        raw_keyframes: list[ReframeKeyframe],
        shot_boundaries: list[int] | None = None,
        face_boxes: list[tuple[int, tuple[float, float, float, float]]] | None = None,
    ) -> list[ReframeKeyframe]:
        """
        Smooth raw crop keyframes while respecting hard cuts and frame bounds.
        """
        if not raw_keyframes:
            return []

        if len(raw_keyframes) == 1:
            kf = raw_keyframes[0]
            cx, cy = self._clamp_center(kf.cx, kf.cy, kf.w, kf.h)
            return [ReframeKeyframe(t_ms=kf.t_ms, cx=cx, cy=cy, w=kf.w, h=kf.h)]

        shot_set = set(shot_boundaries or [])
        face_map = dict(face_boxes or [])

        smoothed: list[ReframeKeyframe] = []
        current_cx = raw_keyframes[0].cx
        current_cy = raw_keyframes[0].cy
        last_t = raw_keyframes[0].t_ms

        for kf in raw_keyframes:
            dt = max(1, kf.t_ms - last_t)
            dt_s = dt / 1000.0

            # 1. Check for shot boundary cut snap
            is_shot_cut = False
            for sb in shot_set:
                if last_t < sb <= kf.t_ms:
                    is_shot_cut = True
                    break

            if is_shot_cut:
                # Snap to new position at shot boundary
                current_cx = kf.cx
                current_cy = kf.cy
            else:
                # 2. Deadzone
                dx = kf.cx - current_cx
                dy = kf.cy - current_cy

                if abs(dx) > self.cfg.deadzone_x:
                    target_x = kf.cx - np.sign(dx) * self.cfg.deadzone_x
                else:
                    target_x = current_cx

                if abs(dy) > self.cfg.deadzone_y:
                    target_y = kf.cy - np.sign(dy) * self.cfg.deadzone_y
                else:
                    target_y = current_cy

                # 3. EMA smoothing
                proposed_cx = current_cx + self.cfg.ema_alpha * (target_x - current_cx)
                proposed_cy = current_cy + self.cfg.ema_alpha * (target_y - current_cy)

                # 4. Max velocity clamp
                max_step = self.cfg.max_pan_speed_per_sec * dt_s
                step_x = np.clip(proposed_cx - current_cx, -max_step, max_step)
                step_y = np.clip(proposed_cy - current_cy, -max_step, max_step)

                current_cx += step_x
                current_cy += step_y

            # 5. Face bounding box containment check
            if kf.t_ms in face_map:
                face_xmin, face_ymin, face_w, face_h = face_map[kf.t_ms]
                face_xmax = face_xmin + face_w
                face_ymax = face_ymin + face_h

                crop_left = current_cx - (kf.w / 2.0)
                crop_right = current_cx + (kf.w / 2.0)
                crop_top = current_cy - (kf.h / 2.0)
                crop_bottom = current_cy + (kf.h / 2.0)

                # Shift crop if face is overflowing left/right
                if face_xmin < crop_left + self.cfg.safe_margin:
                    current_cx = face_xmin - self.cfg.safe_margin + (kf.w / 2.0)
                elif face_xmax > crop_right - self.cfg.safe_margin:
                    current_cx = face_xmax + self.cfg.safe_margin - (kf.w / 2.0)

                # Shift crop if face is overflowing top/bottom
                if face_ymin < crop_top + self.cfg.safe_margin:
                    current_cy = face_ymin - self.cfg.safe_margin + (kf.h / 2.0)
                elif face_ymax > crop_bottom - self.cfg.safe_margin:
                    current_cy = face_ymax + self.cfg.safe_margin - (kf.h / 2.0)

            # 6. Clamp inside frame boundaries [0, 1]
            cx, cy = self._clamp_center(current_cx, current_cy, kf.w, kf.h)
            current_cx, current_cy = cx, cy

            smoothed.append(ReframeKeyframe(
                t_ms=kf.t_ms,
                cx=round(float(cx), 4),
                cy=round(float(cy), 4),
                w=round(float(kf.w), 4),
                h=round(float(kf.h), 4),
            ))

            last_t = kf.t_ms

        return smoothed

    @staticmethod
    def _clamp_center(cx: float, cy: float, w: float, h: float) -> tuple[float, float]:
        """Clamp center coordinates so the crop box stays strictly inside [0, 1]."""
        half_w = w / 2.0
        half_h = h / 2.0

        min_cx = half_w
        max_cx = max(min_cx, 1.0 - half_w)
        clamped_cx = float(np.clip(cx, min_cx, max_cx))

        min_cy = half_h
        max_cy = max(min_cy, 1.0 - half_h)
        clamped_cy = float(np.clip(cy, min_cy, max_cy))

        return clamped_cx, clamped_cy
