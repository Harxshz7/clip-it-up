"""Subtitle chunking, keyword emphasis detection, ASS generation, and preview parity."""
import math
import re
from dataclasses import dataclass, field
from typing import Any

from clip_shared.media.edl import EditDecisionList


@dataclass
class CaptionWord:
    """Word representation in subtitle stream."""
    text: str
    start_ms: int
    end_ms: int
    speaker: str | None = None
    emphasis: bool = False
    deleted: bool = False

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass
class CaptionLine:
    """A chunked display line of 1 or more words."""
    words: list[CaptionWord]
    start_ms: int
    end_ms: int
    speaker: str | None = None

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words if not w.deleted)

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


def detect_emphasis_words(
    words: list[dict[str, Any]],
    target_ratio: float = 0.12,  # 8-15% target
) -> list[bool]:
    """
    Heuristic keyword emphasis detection.
    Identifies impactful words based on:
    - Numbers and numeric quantities ("100", "million", "first")
    - Negations and strong modifiers ("never", "not", "always", "huge", "best", "worst", "insane", "secret")
    - Capitalized acronyms / proper nouns ("AI", "NASA", "Google")
    - Exclamation / question punctuation
    - Word length and rarity heuristics
    Capped at 8-15% of total words.
    """
    n = len(words)
    if n == 0:
        return []

    max_emphasis_count = max(1, int(round(n * min(0.18, max(0.08, target_ratio)))))
    scores: list[float] = [0.0] * n

    STRONG_WORDS = {
        "never", "always", "must", "every", "huge", "massive", "insane", "secret",
        "best", "worst", "stop", "danger", "free", "money", "million", "billion",
        "kill", "win", "lose", "shocking", "truth", "magic", "hack", "mistake",
        "power", "craziest", "genius", "impossible", "easy", "hard", "not", "no",
        "first", "last", "ultimate", "future", "now",
    }

    for i, w in enumerate(words):
        raw = str(w.get("text", w.get("word", "")))
        clean = re.sub(r"[^\w]", "", raw).lower()

        if len(clean) <= 1:
            continue

        score = 0.0

        # Numbers / digits
        if any(char.isdigit() for char in raw):
            score += 3.0

        # Strong vocabulary
        if clean in STRONG_WORDS:
            score += 2.5

        # All-caps word (e.g. NASA, AI, MUST)
        if raw.isupper() and len(raw) >= 2:
            score += 2.0

        # Exclamation mark
        if "!" in raw:
            score += 1.5

        # Word length bonus (longer words tend to carry more semantic weight)
        if len(clean) >= 8:
            score += 1.0

        # Duration bonus: spoken significantly longer than average
        dur_ms = int(w.get("end_ms", 0)) - int(w.get("start_ms", 0))
        if dur_ms >= 500:
            score += 1.0

        scores[i] = score

    # Select top-k scoring words above a baseline threshold
    indexed_scores = [(score, i) for i, score in enumerate(scores) if score >= 1.5]
    indexed_scores.sort(key=lambda x: x[0], reverse=True)

    emphasis_flags = [False] * n
    selected_count = 0

    # Ensure we don't have 2 consecutive emphasized words
    last_idx = -999
    for _, idx in indexed_scores:
        if selected_count >= max_emphasis_count:
            break
        if abs(idx - last_idx) > 1:
            emphasis_flags[idx] = True
            selected_count += 1
            last_idx = idx

    # If too few were selected, pick the highest duration content word
    if selected_count == 0 and n > 0:
        longest_idx = max(range(n), key=lambda idx: int(words[idx].get("end_ms", 0)) - int(words[idx].get("start_ms", 0)))
        emphasis_flags[longest_idx] = True

    return emphasis_flags


def build_clip_captions_data(
    words: list[dict[str, Any]],
    clip_start_ms: int,
    clip_end_ms: int,
    style_key: str = "bold_pop",
    language: str = "en",
) -> list[dict[str, Any]]:
    """
    Extract words inside [clip_start_ms, clip_end_ms] in SOURCE time and annotate keyword emphasis.
    Style-agnostic word data representation.
    """
    clip_words: list[dict[str, Any]] = []

    for w in words:
        start_ms = int(w.get("start_ms", 0))
        end_ms = int(w.get("end_ms", 0))
        text = str(w.get("text", w.get("word", ""))).strip()

        if not text:
            continue

        # Check bounds
        if end_ms <= clip_start_ms or start_ms >= clip_end_ms:
            continue

        clip_words.append({
            "text": text,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "speaker": w.get("speaker"),
            "emphasis": bool(w.get("emphasis", False)),
            "deleted": bool(w.get("deleted", False)),
        })

    # Auto-detect emphasis if not already present
    if clip_words and not any(w["emphasis"] for w in clip_words):
        flags = detect_emphasis_words(clip_words)
        for i, flag in enumerate(flags):
            clip_words[i]["emphasis"] = flag

    return clip_words


def chunk_words_into_lines(
    words: list[CaptionWord | dict[str, Any]],
    max_chars_per_line: int = 24,
    max_lines: int = 2,
    words_per_chunk: int = 3,
    min_duration_ms: int = 250,
) -> list[CaptionLine]:
    """
    Chunk words into timed display lines based on style spec, punctuation boundaries,
    speaker transitions, and pause thresholds.
    """
    parsed_words: list[CaptionWord] = []
    for w in words:
        if isinstance(w, dict):
            if not w.get("deleted", False):
                parsed_words.append(
                    CaptionWord(
                        text=str(w.get("text", "")).strip(),
                        start_ms=int(w.get("start_ms", 0)),
                        end_ms=int(w.get("end_ms", 0)),
                        speaker=w.get("speaker"),
                        emphasis=bool(w.get("emphasis", False)),
                        deleted=bool(w.get("deleted", False)),
                    )
                )
        elif not w.deleted:
            parsed_words.append(w)

    if not parsed_words:
        return []

    lines: list[CaptionLine] = []
    current_chunk: list[CaptionWord] = []

    def flush_chunk():
        nonlocal current_chunk
        if not current_chunk:
            return
        line_start = current_chunk[0].start_ms
        line_end = max(line_start + min_duration_ms, current_chunk[-1].end_ms)
        speaker = current_chunk[0].speaker
        lines.append(
            CaptionLine(
                words=list(current_chunk),
                start_ms=line_start,
                end_ms=line_end,
                speaker=speaker,
            )
        )
        current_chunk = []

    for i, w in enumerate(parsed_words):
        if not current_chunk:
            current_chunk.append(w)
            continue

        # Check speaker change
        if w.speaker and current_chunk[-1].speaker and w.speaker != current_chunk[-1].speaker:
            flush_chunk()
            current_chunk.append(w)
            continue

        # Check pause boundary (> 300ms gap)
        if w.start_ms - current_chunk[-1].end_ms >= 300:
            flush_chunk()
            current_chunk.append(w)
            continue

        # Check punctuation break on previous word (. ? !)
        prev_text = current_chunk[-1].text
        if prev_text.endswith((".", "!", "?")):
            flush_chunk()
            current_chunk.append(w)
            continue

        # Check length & word count limits
        candidate_text = " ".join([cw.text for cw in current_chunk] + [w.text])
        if len(candidate_text) > max_chars_per_line or len(current_chunk) >= words_per_chunk:
            flush_chunk()
            current_chunk.append(w)
        else:
            current_chunk.append(w)

    flush_chunk()

    # Post-process: adjust adjacent line boundaries so there is no negative or overlapping display duration
    for i in range(len(lines) - 1):
        if lines[i].end_ms > lines[i + 1].start_ms:
            lines[i].end_ms = lines[i + 1].start_ms

    return lines


def _format_ass_time(ms: int) -> str:
    """Format milliseconds into ASS time string H:MM:SS.cs."""
    ms = max(0, ms)
    cs = int((ms % 1000) / 10)  # centiseconds (2 digits)
    total_sec = int(ms / 1000)
    secs = total_sec % 60
    total_min = int(total_sec / 60)
    mins = total_min % 60
    hours = int(total_min / 60)
    return f"{hours}:{mins:02d}:{secs:02d}.{cs:02d}"


def generate_ass_subtitles(
    words: list[dict[str, Any]],
    style_spec: dict[str, Any],
    edl: EditDecisionList,
    width: int = 1080,
    height: int = 1920,
    title: str = "Clip Subtitles",
) -> str:
    """
    Generate Advanced SubStation Alpha (.ass) subtitle file content driven by style_spec.
    Words are remapped onto the output timeline via the EDL.
    Supports Bold Pop, Clean Minimal, and Karaoke Dynamic animations.
    """
    remapped_words = edl.remap_words(words)
    if not remapped_words:
        # Return empty ASS script
        return _build_empty_ass(width, height)

    font_family = style_spec.get("font_family", "Montserrat")
    font_size = int(style_spec.get("font_size_pt", 68))
    font_weight = "1" if str(style_spec.get("font_weight", "900")) in ("700", "800", "900", "bold") else "0"
    primary_color = style_spec.get("primary_color", "&H00FFFFFF")
    highlight_color = style_spec.get("highlight_color", "&H0000E6FF")
    outline_color = style_spec.get("outline_color", "&H00000000")
    outline_width = float(style_spec.get("outline_width", 5.0))
    shadow_color = style_spec.get("shadow_color", "&H80000000")
    shadow_offset = float(style_spec.get("shadow_offset", 2.0))
    alignment = int(style_spec.get("alignment", 2))  # 2 = Bottom-Center
    margin_v = int(style_spec.get("margin_v", 280))
    margin_h = int(style_spec.get("margin_h", 60))
    uppercase = bool(style_spec.get("uppercase", False))
    animation = style_spec.get("animation", "pop")  # pop | none | karaoke

    max_chars = int(style_spec.get("max_chars_per_line", 24))
    words_per_chunk = int(style_spec.get("words_per_chunk", 3))

    lines = chunk_words_into_lines(
        words=remapped_words,
        max_chars_per_line=max_chars,
        words_per_chunk=words_per_chunk,
    )

    events: list[str] = []

    for line in lines:
        start_ass = _format_ass_time(line.start_ms)
        end_ass = _format_ass_time(line.end_ms)

        if animation == "karaoke":
            # Generate \k tags with centisecond timings per word
            dialog_parts = []
            for w in line.words:
                w_text = w.text.upper() if uppercase else w.text
                dur_cs = max(1, int(w.duration_ms / 10))
                # If word has emphasis, highlight in special color
                if w.emphasis:
                    dialog_parts.append(f"{{\\c{highlight_color}\\k{dur_cs}}}{w_text} ")
                else:
                    dialog_parts.append(f"{{\\k{dur_cs}}}{w_text} ")
            text_event = "".join(dialog_parts).strip()
            events.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text_event}")

        elif animation == "pop":
            # Word-by-word active pop highlight
            for active_idx, active_w in enumerate(line.words):
                w_start_ass = _format_ass_time(active_w.start_ms)
                w_end_ass = _format_ass_time(active_w.end_ms)

                dialog_parts = []
                for idx, w in enumerate(line.words):
                    w_text = w.text.upper() if uppercase else w.text
                    if idx == active_idx:
                        # Pop animation: scale 115% then settle to 100% with highlight color
                        pop_tag = f"{{\\c{highlight_color}\\t(0,80,\\fscx115\\fscy115)\\t(80,160,\\fscx100\\fscy100)}}"
                        dialog_parts.append(f"{pop_tag}{w_text}{{\\rDefault}} ")
                    elif w.emphasis:
                        dialog_parts.append(f"{{\\c{highlight_color}}}{w_text}{{\\rDefault}} ")
                    else:
                        dialog_parts.append(f"{w_text} ")

                text_event = "".join(dialog_parts).strip()
                events.append(f"Dialogue: 0,{w_start_ass},{w_end_ass},Default,,0,0,0,,{text_event}")

        else:
            # Clean minimal / static line
            dialog_parts = []
            for w in line.words:
                w_text = w.text.upper() if uppercase else w.text
                if w.emphasis:
                    dialog_parts.append(f"{{\\c{highlight_color}\\b1}}{w_text}{{\\rDefault}} ")
                else:
                    dialog_parts.append(f"{w_text} ")
            text_event = "".join(dialog_parts).strip()
            events.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text_event}")

    # Build full ASS file
    header = f"""[Script Info]
Title: {title}
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_family},{font_size},{primary_color},&H000000FF,{outline_color},{shadow_color},{font_weight},0,0,0,100,100,0,0,1,{outline_width:.1f},{shadow_offset:.1f},{alignment},{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(events) + "\n"

    return header


def _build_empty_ass(width: int = 1080, height: int = 1920) -> str:
    return f"""[Script Info]
Title: Empty Subtitles
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat,68,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5.0,2.0,2,60,60,280,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
