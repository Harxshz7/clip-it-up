"""FFmpeg filtergraph generator for 9:16 vertical cropping and fit_blur rendering."""
from typing import Any

from clip_shared.schemas.reframe import ReframeCropPath, ReframeKeyframe


def crop_path_to_ffmpeg_filter(
    crop_path: ReframeCropPath | dict[str, Any],
    src_w: int = 1280,
    src_h: int = 720,
    out_w: int = 1080,
    out_h: int = 1920,
) -> str:
    """
    Generate an FFmpeg -filter_complex / -vf string from a normalized 9:16 crop path.
    Supports both static/dynamic crop + scale and fit_blur background scaling.
    """
    if isinstance(crop_path, dict):
        keyframes_data = crop_path.get("keyframes", [])
        keyframes = [ReframeKeyframe(**k) if isinstance(k, dict) else k for k in keyframes_data]
        segments = crop_path.get("segments", [])
    else:
        keyframes = crop_path.keyframes
        segments = crop_path.segments or []

    # Check if fit_blur mode is requested
    is_fit_blur = any(s.get("mode") == "fit_blur" if isinstance(s, dict) else getattr(s, "mode", None) == "fit_blur" for s in segments)

    if is_fit_blur or not keyframes:
        # 9:16 Fit Blur filtergraph: Blurred zoomed copy as background, original centered in middle
        return (
            f"[0:v]split=2[bg][fg];"
            f"[bg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},boxblur=20:2[bg_blur];"
            f"[fg]scale={out_w}:-2[fg_scaled];"
            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2"
        )

    # Compute crop pixel dimensions from the first/representative keyframe
    ref_kf = keyframes[0]
    crop_w_px = max(2, int(round(ref_kf.w * src_w)))
    crop_h_px = max(2, int(round(ref_kf.h * src_h)))

    # Ensure even dimensions for video codecs
    if crop_w_px % 2 != 0:
        crop_w_px -= 1
    if crop_h_px % 2 != 0:
        crop_h_px -= 1

    if len(keyframes) == 1:
        # Static single crop
        cx_norm = ref_kf.cx
        cy_norm = ref_kf.cy
        crop_x_px = int(np_clip(cx_norm * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px))
        crop_y_px = int(np_clip(cy_norm * src_h - (crop_h_px / 2.0), 0, src_h - crop_h_px))

        return f"crop={crop_w_px}:{crop_h_px}:{crop_x_px}:{crop_y_px},scale={out_w}:{out_h}"

    # Multiple keyframes: construct dynamic time-dependent crop expression or average position
    # For robust FFmpeg compatibility, generate piecewise linear expression for x:
    x_expr_parts = []
    y_expr_parts = []

    # First keyframe base
    t0_s = keyframes[0].t_ms / 1000.0
    x0_px = int(np_clip(keyframes[0].cx * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px))
    y0_px = int(np_clip(keyframes[0].cy * src_h - (crop_h_px / 2.0), 0, src_h - crop_h_px))

    # If motion is minimal (< 20px across full clip), use static average to avoid ffmpeg jitter
    all_x = [int(k.cx * src_w - (crop_w_px / 2.0)) for k in keyframes]
    all_y = [int(k.cy * src_h - (crop_h_px / 2.0)) for k in keyframes]

    if max(all_x) - min(all_x) < 20 and max(all_y) - min(all_y) < 20:
        avg_x = int(np_clip(sum(all_x) / len(all_x), 0, src_w - crop_w_px))
        avg_y = int(np_clip(sum(all_y) / len(all_y), 0, src_h - crop_h_px))
        return f"crop={crop_w_px}:{crop_h_px}:{avg_x}:{avg_y},scale={out_w}:{out_h}"

    # Build piecewise expression
    expr_x = f"{x0_px}"
    for i in range(1, len(keyframes)):
        k_prev = keyframes[i - 1]
        k_curr = keyframes[i]
        t_prev = k_prev.t_ms / 1000.0
        t_curr = k_curr.t_ms / 1000.0
        dt = max(0.001, t_curr - t_prev)

        xp = int(np_clip(k_prev.cx * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px))
        xc = int(np_clip(k_curr.cx * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px))

        # if (t >= t_prev && t < t_curr) => linear interpolate
        lerp = f"if(gte(t,{t_prev:.2f})*lt(t,{t_curr:.2f}),{xp}+({xc}-{xp})*(t-{t_prev:.2f})/{dt:.2f},"
        x_expr_parts.append(lerp)

    expr_x = "".join(x_expr_parts) + f"{all_x[-1]}" + (")" * len(x_expr_parts))
    avg_y = int(np_clip(sum(all_y) / len(all_y), 0, src_h - crop_h_px))

    return f"crop=w={crop_w_px}:h={crop_h_px}:x='{expr_x}':y={avg_y},scale={out_w}:{out_h}"


def np_clip(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))
