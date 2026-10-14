"""Validation engine for Brand Kit assets: logos, custom fonts, intro/outro video clips."""
import os
import re
from typing import Any
import xml.etree.ElementTree as ET

from PIL import Image
from fontTools.ttLib import TTFont

from clip_shared.media.ffmpeg import MediaValidationError, probe_video


# Common unicode ranges for validation
LATIN_BASIC_RANGE = range(0x0020, 0x007F)  # Printable ASCII
INDIC_RANGES = [
    (0x0900, 0x097F),  # Devanagari (Hindi, Marathi, Sanskrit)
    (0x0980, 0x09FF),  # Bengali / Assamese
    (0x0A80, 0x0AFF),  # Gujarati
    (0x0B80, 0x0BFF),  # Tamil
    (0x0C00, 0x0C7F),  # Telugu
    (0x0C80, 0x0CFF),  # Kannada
    (0x0D00, 0x0D7F),  # Malayalam
]


def validate_logo_asset(
    file_path: str,
    max_size_bytes: int = 5 * 1024 * 1024,
) -> dict[str, Any]:
    """
    Validate logo image file (PNG, WebP, SVG).
    Verifies decodability, dimension bounds, and transparency/alpha channel.
    """
    if not os.path.exists(file_path):
        raise MediaValidationError("FILE_NOT_FOUND", f"Logo file {file_path} not found.")

    size_bytes = os.path.getsize(file_path)
    if size_bytes == 0:
        raise MediaValidationError("EMPTY_FILE", "Uploaded logo is empty.")
    if size_bytes > max_size_bytes:
        raise MediaValidationError(
            "LOGO_TOO_LARGE",
            f"Logo size ({size_bytes / (1024*1024):.1f}MB) exceeds limit ({max_size_bytes / (1024*1024):.1f}MB).",
        )

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".svg":
        # Basic SVG validation
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            tag = root.tag.lower()
            if not tag.endswith("svg"):
                raise MediaValidationError("INVALID_SVG", "SVG root element must be <svg>.")
            return {
                "format": "svg",
                "width": 512,
                "height": 512,
                "has_alpha": True,
                "size_bytes": size_bytes,
            }
        except ET.ParseError as e:
            raise MediaValidationError("INVALID_SVG", f"Malformed SVG XML: {str(e)}") from e

    # Raster formats: PNG, WebP
    try:
        with Image.open(file_path) as img:
            img_format = (img.format or "").upper()
            if img_format not in ("PNG", "WEBP"):
                raise MediaValidationError(
                    "UNSUPPORTED_FORMAT",
                    f"Unsupported logo format '{img_format}'. Only PNG, WebP, and SVG are supported.",
                )

            w, h = img.size
            if w < 16 or h < 16:
                raise MediaValidationError("LOGO_TOO_SMALL", f"Logo dimensions {w}x{h} are too small (minimum 16x16).")
            if w > 4096 or h > 4096:
                raise MediaValidationError("LOGO_TOO_LARGE", f"Logo dimensions {w}x{h} exceed 4096x4096px limit.")

            # Check alpha channel
            has_alpha = img.mode in ("RGBA", "LA", "PA") or (
                img.mode == "P" and "transparency" in img.info
            )

            return {
                "format": img_format.lower(),
                "width": w,
                "height": h,
                "has_alpha": has_alpha,
                "size_bytes": size_bytes,
            }
    except MediaValidationError:
        raise
    except Exception as e:
        raise MediaValidationError("CORRUPT_IMAGE", f"Could not decode logo image: {str(e)}") from e


def validate_font_asset(
    file_path: str,
    max_size_bytes: int = 15 * 1024 * 1024,
    license_acknowledged: bool = True,
) -> dict[str, Any]:
    """
    Validate custom font asset (TTF, OTF, WOFF2).
    Verifies font structure, family name, Latin glyph coverage, and warns if Indic coverage is missing.
    """
    if not license_acknowledged:
        raise MediaValidationError(
            "LICENSE_REQUIRED",
            "You must acknowledge that you hold the rights or commercial license to use this font.",
        )

    if not os.path.exists(file_path):
        raise MediaValidationError("FILE_NOT_FOUND", f"Font file {file_path} not found.")

    size_bytes = os.path.getsize(file_path)
    if size_bytes == 0:
        raise MediaValidationError("EMPTY_FILE", "Uploaded font file is empty.")
    if size_bytes > max_size_bytes:
        raise MediaValidationError(
            "FONT_TOO_LARGE",
            f"Font size ({size_bytes / (1024*1024):.1f}MB) exceeds limit ({max_size_bytes / (1024*1024):.1f}MB).",
        )

    try:
        font = TTFont(file_path)
    except Exception as e:
        raise MediaValidationError("INVALID_FONT", f"Invalid font file or unsupported format: {str(e)}") from e

    # Extract font family name
    family_name = "Custom Font"
    full_name = "Custom Font"
    try:
        name_table = font.get("name")
        if name_table:
            for record in name_table.names:
                # 1 = Font Family, 4 = Full Name
                if record.nameID == 1 and family_name == "Custom Font":
                    family_name = record.toUnicode()
                elif record.nameID == 4 and full_name == "Custom Font":
                    full_name = record.toUnicode()
    except Exception:
        pass

    # Extract cmap (character map)
    cmap = font.getBestCmap() or {}
    if not cmap:
        raise MediaValidationError("NO_GLYPHS", "Font contains no usable character map (cmap).")

    # Verify Latin coverage (printable ASCII)
    missing_latin = [cp for cp in LATIN_BASIC_RANGE if cp not in cmap]
    if len(missing_latin) > 15:  # Allow missing some rare symbols, but require bulk of ASCII
        raise MediaValidationError(
            "INSUFFICIENT_GLYPH_COVERAGE",
            f"Font is missing {len(missing_latin)} basic Latin characters and cannot be used for subtitles.",
        )

    # Check Indic coverage
    has_indic = False
    for start, end in INDIC_RANGES:
        for cp in range(start, end + 1):
            if cp in cmap:
                has_indic = True
                break
        if has_indic:
            break

    warning = None
    if not has_indic:
        warning = "Font lacks Indic glyph coverage (Devanagari/regional scripts); fallback font will be used for Indic text."

    return {
        "font_family": family_name,
        "full_name": full_name,
        "glyph_count": len(cmap),
        "has_indic": has_indic,
        "warning": warning,
        "size_bytes": size_bytes,
    }


def validate_video_asset(
    file_path: str,
    kind: str = "intro",
    max_duration_s: float = 10.0,
    max_size_bytes: int = 50 * 1024 * 1024,
) -> dict[str, Any]:
    """
    Validate intro or outro MP4 clip.
    Verifies video stream, audio stream, and enforces maximum duration limit.
    """
    if not os.path.exists(file_path):
        raise MediaValidationError("FILE_NOT_FOUND", f"{kind.capitalize()} file {file_path} not found.")

    size_bytes = os.path.getsize(file_path)
    if size_bytes == 0:
        raise MediaValidationError("EMPTY_FILE", f"Uploaded {kind} video is empty.")
    if size_bytes > max_size_bytes:
        raise MediaValidationError(
            "VIDEO_TOO_LARGE",
            f"{kind.capitalize()} video size ({size_bytes / (1024*1024):.1f}MB) exceeds limit ({max_size_bytes / (1024*1024):.1f}MB).",
        )

    meta = probe_video(file_path, max_duration_min=5)

    if meta.duration_seconds > (max_duration_s + 0.2):  # 200ms grace window
        raise MediaValidationError(
            "VIDEO_TOO_LONG",
            f"{kind.capitalize()} video duration ({meta.duration_seconds:.1f}s) exceeds maximum allowed {max_duration_s:.1f}s for your plan.",
        )

    return {
        "duration_ms": int(meta.duration_seconds * 1000),
        "width": meta.width,
        "height": meta.height,
        "fps": meta.fps,
        "has_audio": meta.has_audio,
        "video_codec": meta.video_codec,
        "size_bytes": size_bytes,
    }
