"""FFmpeg filtergraph generator for 9:16 vertical cropping, multi-person split_stack, pip, stack, and fit_blur rendering."""
from typing import Any

from clip_shared.schemas.reframe import ReframeCropPath, ReframeKeyframe, ReframeLayout


def np_clip(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))


def crop_path_to_ffmpeg_filter(
    crop_path: ReframeCropPath | dict[str, Any],
    src_w: int = 1280,
    src_h: int = 720,
    out_w: int = 1080,
    out_h: int = 1920,
    in_label: str = "0:v",
    out_label: str | None = None,
) -> str:
    """
    Generate an FFmpeg filtergraph string from a normalized 9:16 crop path and layout specification.
    Supports:
    - speaker_track / balanced / center (crop + scale)
    - fit_blur / content_fit (background blur + centered 16:9 content)
    - content_zoom (ROI crop + scale)
    - split_stack (two stacked 1080x960 crops using vstack)
    - stack (60% content on top, 40% speaker below using vstack)
    - pip (full-frame content with circular/rounded speaker PIP in safe corner)
    """
    if isinstance(crop_path, dict):
        keyframes_data = crop_path.get("keyframes", [])
        keyframes = [ReframeKeyframe(**k) if isinstance(k, dict) else k for k in keyframes_data]
        segments = crop_path.get("segments", [])
        layout_data = crop_path.get("layout")
    else:
        keyframes = crop_path.keyframes
        segments = crop_path.segments or []
        layout_data = crop_path.layout

    # Check primary mode across segments
    mode = "speaker_track"
    if segments:
        first_seg = segments[0]
        mode = first_seg.get("mode") if isinstance(first_seg, dict) else getattr(first_seg, "mode", "speaker_track")

    layout_type = None
    regions = []
    if layout_data:
        layout_type = layout_data.get("type") if isinstance(layout_data, dict) else getattr(layout_data, "type", None)
        regions = layout_data.get("regions", []) if isinstance(layout_data, dict) else getattr(layout_data, "regions", [])

    active_mode = layout_type or mode

    # 1. SPLIT STACK LAYOUT (2 faces stacked top/bottom, 1080x960 each)
    if active_mode == "split_stack":
        half_h = out_h // 2  # 960
        # Determine regions for top and bottom faces
        if len(regions) >= 2:
            r0 = regions[0] if isinstance(regions[0], dict) else regions[0].model_dump()
            r1 = regions[1] if isinstance(regions[1], dict) else regions[1].model_dump()
            t_cx, t_cy = r0.get("src_x", 0.35) + r0.get("src_w", 0.3) / 2.0, r0.get("src_y", 0.35) + r0.get("src_h", 0.3) / 2.0
            b_cx, b_cy = r1.get("src_x", 0.65) + r1.get("src_w", 0.3) / 2.0, r1.get("src_y", 0.35) + r1.get("src_h", 0.3) / 2.0
        else:
            t_cx, t_cy = 0.35, 0.40
            b_cx, b_cy = 0.65, 0.40

        # Sub-crop dimensions: 9:8 aspect ratio (out_w / half_h = 1080 / 960 = 1.125)
        sub_aspect = out_w / float(half_h)
        sub_h_px = src_h
        sub_w_px = int(round(src_h * sub_aspect * (720 / 1280.0)))  # proportional
        sub_w_px = min(src_w, max(120, int(src_w * 0.45)))
        sub_h_px = int(sub_w_px / sub_aspect)
        if sub_w_px % 2 != 0: sub_w_px -= 1
        if sub_h_px % 2 != 0: sub_h_px -= 1

        top_x = int(np_clip(t_cx * src_w - (sub_w_px / 2.0), 0, src_w - sub_w_px))
        top_y = int(np_clip(t_cy * src_h - (sub_h_px / 2.0), 0, src_h - sub_h_px))
        bot_x = int(np_clip(b_cx * src_w - (sub_w_px / 2.0), 0, src_w - sub_w_px))
        bot_y = int(np_clip(b_cy * src_h - (sub_h_px / 2.0), 0, src_h - sub_h_px))

        out_suffix = f"[{out_label}]" if out_label else ""
        return (
            f"[{in_label}]split=2[t_in][b_in];"
            f"[t_in]crop={sub_w_px}:{sub_h_px}:{top_x}:{top_y},scale={out_w}:{half_h}[top];"
            f"[b_in]crop={sub_w_px}:{sub_h_px}:{bot_x}:{bot_y},scale={out_w}:{half_h}[bot];"
            f"[top][bot]vstack=inputs=2{out_suffix}"
        )

    # 2. STACK LAYOUT (Content ~60% on top, Speaker ~40% below)
    if active_mode == "stack":
        top_h = int(out_h * 0.60)  # 1152
        bot_h = out_h - top_h      # 768

        if len(regions) >= 2:
            r_c = regions[0] if isinstance(regions[0], dict) else regions[0].model_dump()
            r_s = regions[1] if isinstance(regions[1], dict) else regions[1].model_dump()
            c_x = int(r_c.get("src_x", 0.0) * src_w)
            c_y = int(r_c.get("src_y", 0.0) * src_h)
            c_w = int(r_c.get("src_w", 1.0) * src_w)
            c_h = int(r_c.get("src_h", 1.0) * src_h)
            s_cx = r_s.get("src_x", 0.5) + r_s.get("src_w", 0.2) / 2.0
            s_cy = r_s.get("src_y", 0.3) + r_s.get("src_h", 0.2) / 2.0
        else:
            c_x, c_y, c_w, c_h = 0, 0, src_w, src_h
            s_cx, s_cy = 0.5, 0.4

        if c_w % 2 != 0: c_w -= 1
        if c_h % 2 != 0: c_h -= 1
        spk_w = int(src_w * 0.40)
        spk_h = int(spk_w * (bot_h / float(out_w)))
        if spk_w % 2 != 0: spk_w -= 1
        if spk_h % 2 != 0: spk_h -= 1
        s_x = int(np_clip(s_cx * src_w - (spk_w / 2.0), 0, src_w - spk_w))
        s_y = int(np_clip(s_cy * src_h - (spk_h / 2.0), 0, src_h - spk_h))

        out_suffix = f"[{out_label}]" if out_label else ""
        return (
            f"[{in_label}]split=2[c_in][s_in];"
            f"[c_in]crop={c_w}:{c_h}:{c_x}:{c_y},scale={out_w}:{top_h}[top];"
            f"[s_in]crop={spk_w}:{spk_h}:{s_x}:{s_y},scale={out_w}:{bot_h}[bot];"
            f"[top][bot]vstack=inputs=2{out_suffix}"
        )

    # 3. PIP LAYOUT (Full content with speaker cutout overlay)
    if active_mode == "pip":
        # PIP size ~25% of output width
        pip_w = int(out_w * 0.28)
        pip_h = int(pip_w * 1.15)
        if pip_w % 2 != 0: pip_w -= 1
        if pip_h % 2 != 0: pip_h -= 1

        # Safe corner coordinates (top-right safe zone: x=W-w-50, y=140)
        pip_x = f"W-w-50"
        pip_y = "140"

        # Speaker crop
        spk_crop_w = int(src_w * 0.25)
        spk_crop_h = int(src_h * 0.35)
        if spk_crop_w % 2 != 0: spk_crop_w -= 1
        if spk_crop_h % 2 != 0: spk_crop_h -= 1

        if len(regions) >= 2:
            r_s = regions[1] if isinstance(regions[1], dict) else regions[1].model_dump()
            spk_cx = r_s.get("src_x", 0.85) + r_s.get("src_w", 0.15) / 2.0
            spk_cy = r_s.get("src_y", 0.15) + r_s.get("src_h", 0.15) / 2.0
        else:
            spk_cx, spk_cy = 0.85, 0.20

        spk_x = int(np_clip(spk_cx * src_w - (spk_crop_w / 2.0), 0, src_w - spk_crop_w))
        spk_y = int(np_clip(spk_cy * src_h - (spk_crop_h / 2.0), 0, src_h - spk_crop_h))

        out_suffix = f"[{out_label}]" if out_label else ""
        return (
            f"[{in_label}]split=2[main_src][pip_src];"
            f"[main_src]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},boxblur=20:2[bg_blur];"
            f"[{in_label}]scale={out_w}:-2[fg_scaled];"
            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2[base];"
            f"[pip_src]crop={spk_crop_w}:{spk_crop_h}:{spk_x}:{spk_y},scale={pip_w}:{pip_h}[pip];"
            f"[base][pip]overlay={pip_x}:{pip_y}{out_suffix}"
        )

    # 4. CONTENT FIT / FIT BLUR
    if active_mode in ("fit_blur", "content_fit") or not keyframes:
        out_suffix = f"[{out_label}]" if out_label else ""
        return (
            f"[{in_label}]split=2[bg][fg];"
            f"[bg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},boxblur=20:2[bg_blur];"
            f"[fg]scale={out_w}:-2[fg_scaled];"
            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2{out_suffix}"
        )

    # 5. CROP + SCALE (speaker_track, balanced, center, content_zoom)
    ref_kf = keyframes[0]
    crop_w_px = max(2, int(round(ref_kf.w * src_w)))
    crop_h_px = max(2, int(round(ref_kf.h * src_h)))

    if crop_w_px % 2 != 0: crop_w_px -= 1
    if crop_h_px % 2 != 0: crop_h_px -= 1

    out_suffix = f"[{out_label}]" if out_label else ""

    if len(keyframes) == 1:
        cx_norm = ref_kf.cx
        cy_norm = ref_kf.cy
        crop_x_px = int(np_clip(cx_norm * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px))
        crop_y_px = int(np_clip(cy_norm * src_h - (crop_h_px / 2.0), 0, src_h - crop_h_px))
        prefix = f"[{in_label}]" if in_label != "0:v" else ""
        return f"{prefix}crop={crop_w_px}:{crop_h_px}:{crop_x_px}:{crop_y_px},scale={out_w}:{out_h}{out_suffix}"

    all_x = [int(k.cx * src_w - (crop_w_px / 2.0)) for k in keyframes]
    all_y = [int(k.cy * src_h - (crop_h_px / 2.0)) for k in keyframes]

    # Minimal motion: static average
    if max(all_x) - min(all_x) < 20 and max(all_y) - min(all_y) < 20:
        avg_x = int(np_clip(sum(all_x) / len(all_x), 0, src_w - crop_w_px))
        avg_y = int(np_clip(sum(all_y) / len(all_y), 0, src_h - crop_h_px))
        prefix = f"[{in_label}]" if in_label != "0:v" else ""
        return f"{prefix}crop={crop_w_px}:{crop_h_px}:{avg_x}:{avg_y},scale={out_w}:{out_h}{out_suffix}"

    x_expr_parts = []
    x0_px = int(np_clip(keyframes[0].cx * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px))

    for i in range(1, len(keyframes)):
        k_prev = keyframes[i - 1]
        k_curr = keyframes[i]
        t_prev = k_prev.t_ms / 1000.0
        t_curr = k_curr.t_ms / 1000.0
        dt = max(0.001, t_curr - t_prev)

        xp = int(np_clip(k_prev.cx * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px))
        xc = int(np_clip(k_curr.cx * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px))
        lerp = f"if(gte(t,{t_prev:.2f})*lt(t,{t_curr:.2f}),{xp}+({xc}-{xp})*(t-{t_prev:.2f})/{dt:.2f},"
        x_expr_parts.append(lerp)

    expr_x = "".join(x_expr_parts) + f"{all_x[-1]}" + (")" * len(x_expr_parts))
    avg_y = int(np_clip(sum(all_y) / len(all_y), 0, src_h - crop_h_px))
    prefix = f"[{in_label}]" if in_label != "0:v" else ""
    return f"{prefix}crop=w={crop_w_px}:h={crop_h_px}:x='{expr_x}':y={avg_y},scale={out_w}:{out_h}{out_suffix}"
