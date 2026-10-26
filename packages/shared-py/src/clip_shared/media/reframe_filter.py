"""Helper to generate crop and layout scaling filters for vertical reframing."""
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

    all_x = [int(np_clip(float(k.get("cx", 0.5)) * src_w - (crop_w_px / 2.0), 0, src_w - crop_w_px)) for k in keyframes]
    all_y = [int(np_clip(float(k.get("cy", 0.5)) * src_h - (crop_h_px / 2.0), 0, src_h - crop_h_px)) for k in keyframes]

    if max(all_x) - min(all_x) < 25 and max(all_y) - min(all_y) < 25:
        avg_x = int(sum(all_x) / len(all_x))
        avg_y = int(sum(all_y) / len(all_y))
        return f"crop={crop_w_px}:{crop_h_px}:{avg_x}:{avg_y}"

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


def compile_layout_reframe_filter(
    crop_path: dict[str, Any],
    src_w: int = 1280,
    src_h: int = 720,
    out_w: int = 1080,
    out_h: int = 1920,
    in_label: str = "v_cat",
    out_label: str = "v_reframe",
) -> str:
    """
    Compile complex layout (split_stack, stack, pip, content_fit) into FFmpeg filtergraph lines.
    """
    segments = crop_path.get("segments", [])
    layout_data = crop_path.get("layout") or {}
    first_mode = segments[0].get("mode") if segments else "speaker_track"
    active_mode = layout_data.get("type") or first_mode
    regions = layout_data.get("regions", [])

    if active_mode == "split_stack":
        half_h = out_h // 2
        if len(regions) >= 2:
            r0 = regions[0]
            r1 = regions[1]
            t_cx = r0.get("src_x", 0.35) + r0.get("src_w", 0.3) / 2.0
            t_cy = r0.get("src_y", 0.35) + r0.get("src_h", 0.3) / 2.0
            b_cx = r1.get("src_x", 0.65) + r1.get("src_w", 0.3) / 2.0
            b_cy = r1.get("src_y", 0.35) + r1.get("src_h", 0.3) / 2.0
        else:
            t_cx, t_cy = 0.35, 0.40
            b_cx, b_cy = 0.65, 0.40

        sub_w_px = min(src_w, max(120, int(src_w * 0.45)))
        sub_h_px = int(sub_w_px / 1.125)
        if sub_w_px % 2 != 0: sub_w_px -= 1
        if sub_h_px % 2 != 0: sub_h_px -= 1

        top_x = int(np_clip(t_cx * src_w - (sub_w_px / 2.0), 0, src_w - sub_w_px))
        top_y = int(np_clip(t_cy * src_h - (sub_h_px / 2.0), 0, src_h - sub_h_px))
        bot_x = int(np_clip(b_cx * src_w - (sub_w_px / 2.0), 0, src_w - sub_w_px))
        bot_y = int(np_clip(b_cy * src_h - (sub_h_px / 2.0), 0, src_h - sub_h_px))

        return (
            f"[{in_label}]split=2[t_in][b_in];"
            f"[t_in]crop={sub_w_px}:{sub_h_px}:{top_x}:{top_y},scale={out_w}:{half_h}[top];"
            f"[b_in]crop={sub_w_px}:{sub_h_px}:{bot_x}:{bot_y},scale={out_w}:{half_h}[bot];"
            f"[top][bot]vstack=inputs=2[{out_label}];"
        )

    if active_mode == "stack":
        top_h = int(out_h * 0.60)
        bot_h = out_h - top_h
        c_w = min(src_w, int(src_w * 0.95))
        c_h = int(c_w * (top_h / float(out_w)))
        if c_w % 2 != 0: c_w -= 1
        if c_h % 2 != 0: c_h -= 1
        c_x = (src_w - c_w) // 2
        c_y = max(0, int(src_h * 0.05))

        spk_w = int(src_w * 0.40)
        spk_h = int(spk_w * (bot_h / float(out_w)))
        if spk_w % 2 != 0: spk_w -= 1
        if spk_h % 2 != 0: spk_h -= 1
        s_x = int(np_clip(0.5 * src_w - (spk_w / 2.0), 0, src_w - spk_w))
        s_y = int(np_clip(0.4 * src_h - (spk_h / 2.0), 0, src_h - spk_h))

        return (
            f"[{in_label}]split=2[c_in][s_in];"
            f"[c_in]crop={c_w}:{c_h}:{c_x}:{c_y},scale={out_w}:{top_h}[top];"
            f"[s_in]crop={spk_w}:{spk_h}:{s_x}:{s_y},scale={out_w}:{bot_h}[bot];"
            f"[top][bot]vstack=inputs=2[{out_label}];"
        )

    if active_mode == "pip":
        pip_w = int(out_w * 0.28)
        pip_h = int(pip_w * 1.15)
        if pip_w % 2 != 0: pip_w -= 1
        if pip_h % 2 != 0: pip_h -= 1
        spk_w = int(src_w * 0.25)
        spk_h = int(src_h * 0.35)
        if spk_w % 2 != 0: spk_w -= 1
        if spk_h % 2 != 0: spk_h -= 1
        spk_x = int(np_clip(0.85 * src_w - (spk_w / 2.0), 0, src_w - spk_w))
        spk_y = int(np_clip(0.20 * src_h - (spk_h / 2.0), 0, src_h - spk_h))

        return (
            f"[{in_label}]split=2[main_src][pip_src];"
            f"[main_src]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h},boxblur=20:2[bg_blur];"
            f"[{in_label}]scale={out_w}:-2[fg_scaled];"
            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2[base];"
            f"[pip_src]crop={spk_w}:{spk_h}:{spk_x}:{spk_y},scale={pip_w}:{pip_h}[pip];"
            f"[base][pip]overlay=W-w-50:140[{out_label}];"
        )

    # Default fit_blur / content_fit
    return (
        f"[{in_label}]split=2[bg][fg];"
        f"[bg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h},boxblur=20:2[bg_blur];"
        f"[{in_label}]scale={out_w}:-2[fg_scaled];"
        f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2[{out_label}];"
    )
