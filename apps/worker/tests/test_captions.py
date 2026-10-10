
from clip_shared.db.seed import DEFAULT_CAPTION_STYLES
from clip_shared.media.captions import (
    chunk_words_into_lines,
    detect_emphasis_words,
    generate_ass_subtitles,
)
from clip_shared.media.edl import EditDecisionList


def test_chunk_words_into_lines_limits_and_breaks():
    """Verify word chunking respects max chars, word limits, punctuation breaks, and pauses."""
    words = [
        {"text": "Welcome", "start_ms": 1000, "end_ms": 1400},
        {"text": "to", "start_ms": 1400, "end_ms": 1600},
        {"text": "the", "start_ms": 1600, "end_ms": 1800},
        {"text": "show!", "start_ms": 1800, "end_ms": 2200},  # Exclamation break
        {"text": "Today", "start_ms": 2300, "end_ms": 2700},
        {"text": "we", "start_ms": 2700, "end_ms": 2900},
        {"text": "build", "start_ms": 2900, "end_ms": 3200},
        {"text": "something", "start_ms": 3200, "end_ms": 3600},
        {"text": "amazing.", "start_ms": 3600, "end_ms": 4000},
    ]

    lines = chunk_words_into_lines(
        words=words,
        max_chars_per_line=20,
        words_per_chunk=3,
        min_duration_ms=250,
    )

    assert len(lines) >= 3
    # First chunk: "Welcome to the"
    assert lines[0].text == "Welcome to the"
    assert lines[0].start_ms == 1000
    # Second chunk: "show!" because of exclamation mark flush
    assert lines[1].text == "show!"
    assert lines[1].start_ms == 1800


def test_detect_emphasis_words():
    """Verify emphasis detection highlights numbers, negations, and high impact words."""
    words = [
        {"text": "You", "start_ms": 0, "end_ms": 200},
        {"text": "will", "start_ms": 200, "end_ms": 400},
        {"text": "never", "start_ms": 400, "end_ms": 800},   # Strong word
        {"text": "believe", "start_ms": 800, "end_ms": 1100},
        {"text": "this", "start_ms": 1100, "end_ms": 1300},
        {"text": "100", "start_ms": 1300, "end_ms": 1600},    # Number
        {"text": "percent", "start_ms": 1600, "end_ms": 1900},
    ]

    flags = detect_emphasis_words(words)
    assert len(flags) == len(words)
    # Check that 'never' or '100' are emphasized
    emphasized_indices = [i for i, f in enumerate(flags) if f]
    assert len(emphasized_indices) >= 1
    assert any(words[i]["text"] in ("never", "100") for i in emphasized_indices)


def test_generate_ass_bold_pop():
    """Verify ASS output generation for Bold Pop style."""
    style_spec = next(s["spec"] for s in DEFAULT_CAPTION_STYLES if s["key"] == "bold_pop")
    words = [
        {"text": "This", "start_ms": 0, "end_ms": 300, "emphasis": False},
        {"text": "is", "start_ms": 300, "end_ms": 500, "emphasis": False},
        {"text": "INSANE!", "start_ms": 500, "end_ms": 1000, "emphasis": True},
    ]
    edl = EditDecisionList.create(clip_start_ms=0, clip_end_ms=2000)
    ass_text = generate_ass_subtitles(words, style_spec, edl)

    # Validations
    assert "[Script Info]" in ass_text
    assert "[V4+ Styles]" in ass_text
    assert "PlayResX: 1080" in ass_text
    assert "PlayResY: 1920" in ass_text
    assert "Style: Default,Montserrat,68" in ass_text
    assert "Dialogue: 0," in ass_text
    assert "\\fscx115" in ass_text  # Pop animation tag
    assert "INSANE!" in ass_text


def test_generate_ass_clean_minimal():
    """Verify ASS output generation for Clean Minimal style."""
    style_spec = next(s["spec"] for s in DEFAULT_CAPTION_STYLES if s["key"] == "clean_minimal")
    words = [
        {"text": "Simple", "start_ms": 0, "end_ms": 400, "emphasis": False},
        {"text": "elegant", "start_ms": 400, "end_ms": 900, "emphasis": True},
        {"text": "design.", "start_ms": 900, "end_ms": 1400, "emphasis": False},
    ]
    edl = EditDecisionList.create(clip_start_ms=0, clip_end_ms=2000)
    ass_text = generate_ass_subtitles(words, style_spec, edl)

    assert "Style: Default,Inter,52" in ass_text
    assert "Dialogue: 0," in ass_text
    assert "elegant" in ass_text


def test_generate_ass_karaoke():
    """Verify ASS output generation with \\k tags for Karaoke style."""
    style_spec = next(s["spec"] for s in DEFAULT_CAPTION_STYLES if s["key"] == "karaoke")
    words = [
        {"text": "Sing", "start_ms": 0, "end_ms": 400, "emphasis": False},
        {"text": "along", "start_ms": 400, "end_ms": 900, "emphasis": True},
        {"text": "now", "start_ms": 900, "end_ms": 1300, "emphasis": False},
    ]
    edl = EditDecisionList.create(clip_start_ms=0, clip_end_ms=2000)
    ass_text = generate_ass_subtitles(words, style_spec, edl)

    assert "Style: Default,Poppins,62" in ass_text
    assert "\\k" in ass_text  # Karaoke duration tags


def test_generate_ass_indic_hindi_kannada():
    """Verify Indic language subtitles (Hindi and Kannada) are properly encoded in UTF-8 ASS."""
    style_spec = next(s["spec"] for s in DEFAULT_CAPTION_STYLES if s["key"] == "clean_minimal")
    words = [
        # Hindi line: यह एक बहुत महत्वपूर्ण बात है
        {"text": "यह", "start_ms": 0, "end_ms": 300, "emphasis": False},
        {"text": "एक", "start_ms": 300, "end_ms": 600, "emphasis": False},
        {"text": "महत्वपूर्ण", "start_ms": 600, "end_ms": 1200, "emphasis": True},
        {"text": "बात", "start_ms": 1200, "end_ms": 1500, "emphasis": False},
        # Kannada line: ಇದು ಅದ್ಭುತವಾದ ವಿಡಿಯೋ
        {"text": "ಇದು", "start_ms": 1600, "end_ms": 2000, "emphasis": False},
        {"text": "ಅದ್ಭುತವಾದ", "start_ms": 2000, "end_ms": 2600, "emphasis": True},
    ]
    edl = EditDecisionList.create(clip_start_ms=0, clip_end_ms=3000)
    ass_text = generate_ass_subtitles(words, style_spec, edl)

    assert "महत्वपूर्ण" in ass_text
    assert "ಅದ್ಭುತವಾದ" in ass_text
    # Verify valid UTF-8 string encoding
    encoded = ass_text.encode("utf-8")
    assert len(encoded) > 0


def test_caption_safe_zone_structural_bounds():
    """Structural test: verify safe zone bottom margin (MarginV=280) and horizontal margin (MarginH=60)."""
    for style in DEFAULT_CAPTION_STYLES:
        spec = style["spec"]
        assert spec["margin_v"] >= 200  # Stays above TikTok/Reels UI
        assert spec["margin_h"] >= 40   # 5% side margins
        assert spec["max_chars_per_line"] <= 40  # Prevents overflowing 1080px width
