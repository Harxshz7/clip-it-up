"""Helper to generate crop and scaling filters for vertical reframing."""
from typing import Any


def np_clip(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))


def reframe_crop_to_filter(
    crop_path: dict[str, Any],
    src_w: int = 1280,
    src_h: int = 720,
    out_w: int = 1080,
    out_h: int = 1920,
) -> str:
    """
    Generate the video crop/reframe filter string from crop_path keyframes.
    Supports single static crop, dynamic piecewise linear crop, and fit_blur fallback.
    """
    keyframes = crop_path.get("keyframes", [])
    if not keyframes:
        # Default center crop
        cw = int(min(src_w, src_h * 9 / 16))
        ch = int(min(src_h, src_w * 16 / 9))
        cx = (src_w - cw) // 2
        cy = (src_h - ch) // 2
        return f"crop={cw}:{ch}:{cx}:{cy}"

    # Reference keyframe dimensions
    ref_kf = keyframes[0]
    kf_w = float(ref_kf.get("w", 0.5625))
    kf_h = float(ref_kf.get("h", 1.0))

    crop_w_px = max(2, int(round(kf_w * src_w)))
    crop_h_px = max(2, int(round(kf_h * src_h)))

    # Ensure even dimensions
    if crop_w_px % 2 != 0:
        crop_w_px -= 1
    if crop_h_px % 2 != 0:
        crop_h_px -= 1

    if len(keyframes) == 1:
        cx_norm = float(ref_kf.get("cx", 0.5))
        cy_norm = float(ref_kf.get("cy", 0.5))
        crop_x_px = int(np_clip(cx_norm * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px))
        crop_y_px = int(np_clip(cy_norm * src_h - (crop_h_px / 2.0), 0, src_h - crop_h_px))
        return f"crop={crop_w_px}:{crop_h_px}:{crop_x_px}:{crop_y_px}"

    # Multiple keyframes
    all_x = [int(np_clip(float(k.get("cx", 0.5)) * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px)) for k in keyframes]
    all_y = [int(np_clip(float(k.get("cy", 0.5)) * src_h - (crop_h_px / 2.0), 0, src_h - crop_h_px)) for k in keyframes]

    # If motion is small (< 25px), use static average to prevent jitter
    if max(all_x) - min(all_x) < 25 and max(all_y) - min(all_y) < 25:
        avg_x = int(sum(all_x) / len(all_x))
        avg_y = int(sum(all_y) / len(all_y))
        return f"crop={crop_w_px}:{crop_h_px}:{avg_x}:{avg_y}"

    # Piecewise linear x interpolation
    x0_px = all_x[0]
    x_expr_parts = []
    for i in range(1, len(keyframes)):
        k_prev = keyframes[i - 1]
        k_curr = keyframes[i]
        t_prev = float(k_prev.get("t_ms", 0)) / 1000.0
        t_curr = float(k_curr.get("t_ms", 0)) / 1000.0
        dt = max(0.001, t_curr - t_prev)
        xp = all_x[i - 1]
        xc = all_x[i]
        lerp = f"if(gte(t,{t_prev:.2f})*lt(t,{t_curr:.2f}),{xp}+({xc}-{xp})*(t-{t_prev:.2f})/{dt:.2f},"
        x_expr_parts.append(lerp)

    expr_x = "".join(x_expr_parts) + f"{all_x[-1]}" + (")" * len(x_expr_parts))
    avg_y = int(sum(all_y) / len(all_y))

    return f"crop=w={crop_w_px}:h={crop_h_px}:x='{expr_x}':y={avg_y}"
