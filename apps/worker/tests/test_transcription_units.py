from worker.transcription.base import SegmentItem, SpeakerItem, TranscriptionResult, WordItem
from worker.transcription.deepgram_backend import DeepgramBackend
from worker.transcription.export import export_json, export_srt, export_txt, export_vtt
from worker.transcription.segment_builder import build_segments_from_words


def test_segment_builder_punctuation_and_speaker_change():
    words = [
        WordItem(idx=0, word="Hello", start_ms=0, end_ms=300, speaker="SPEAKER_00"),
        WordItem(idx=1, word="world.", start_ms=350, end_ms=700, speaker="SPEAKER_00"),
        WordItem(idx=2, word="How", start_ms=800, end_ms=1000, speaker="SPEAKER_01"),
        WordItem(idx=3, word="are", start_ms=1050, end_ms=1200, speaker="SPEAKER_01"),
        WordItem(idx=4, word="you?", start_ms=1250, end_ms=1500, speaker="SPEAKER_01"),
    ]

    segments = build_segments_from_words(words)
    assert len(segments) == 2

    # Segment 1
    assert segments[0].idx == 0
    assert segments[0].speaker == "SPEAKER_00"
    assert segments[0].text == "Hello world."
    assert segments[0].start_ms == 0
    assert segments[0].end_ms == 700
    assert len(segments[0].words) == 2

    # Segment 2
    assert segments[1].idx == 1
    assert segments[1].speaker == "SPEAKER_01"
    assert segments[1].text == "How are you?"
    assert segments[1].start_ms == 800
    assert segments[1].end_ms == 1500
    assert len(segments[1].words) == 3


def test_segment_builder_max_words_splitting():
    words = [
        WordItem(idx=i, word=f"word{i}", start_ms=i * 200, end_ms=(i * 200) + 150, speaker="SPEAKER_00")
        for i in range(40)
    ]

    segments = build_segments_from_words(words, max_words=15)
    assert len(segments) >= 3
    for seg in segments:
        assert len(seg.words) <= 15


def test_export_formatters():
    segments = [
        SegmentItem(idx=0, start_ms=1000, end_ms=3500, speaker="SPEAKER_00", text="Welcome to the show."),
        SegmentItem(idx=1, start_ms=4000, end_ms=7200, speaker="SPEAKER_01", text="Thanks for having me."),
    ]
    speakers_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}

    # 1. TXT
    txt = export_txt(segments, speakers_map)
    assert "[Alice]" in txt
    assert "[Bob]" in txt
    assert "Welcome to the show." in txt

    # 2. SRT
    srt = export_srt(segments, speakers_map)
    assert "00:00:01,000 --> 00:00:03,500" in srt
    assert "[Alice] Welcome to the show." in srt
    assert "00:00:04,000 --> 00:00:07,200" in srt

    # 3. VTT
    vtt = export_vtt(segments, speakers_map)
    assert "WEBVTT" in vtt
    assert "00:00:01.000 --> 00:00:03.500" in vtt
    assert "<v Alice>Welcome to the show." in vtt

    # 4. JSON
    res = TranscriptionResult(
        language="en",
        status="ready",
        model="test-v1",
        backend="mock",
        word_count=8,
        words=[],
        segments=segments,
        speakers=[SpeakerItem(label="SPEAKER_00", display_name="Alice")],
    )
    json_str = export_json(res, speakers_map)
    assert '"model": "test-v1"' in json_str
    assert '"display_name": "Alice"' in json_str


def test_deepgram_mapping():
    deepgram_payload = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "languages": ["en"],
                            "words": [
                                {
                                    "word": "hello",
                                    "punctuated_word": "Hello,",
                                    "start": 0.5,
                                    "end": 0.9,
                                    "speaker": 0,
                                    "confidence": 0.98,
                                },
                                {
                                    "word": "everyone",
                                    "punctuated_word": "everyone.",
                                    "start": 1.0,
                                    "end": 1.5,
                                    "speaker": 1,
                                    "confidence": 0.95,
                                },
                            ],
                        }
                    ]
                }
            ]
        }
    }

    result = DeepgramBackend.map_deepgram_response(deepgram_payload)
    assert result.backend == "deepgram"
    assert result.language == "en"
    assert result.word_count == 2
    assert len(result.words) == 2
    assert result.words[0].word == "Hello,"
    assert result.words[0].start_ms == 500
    assert result.words[0].end_ms == 900
    assert result.words[0].speaker == "SPEAKER_00"
    assert result.words[1].speaker == "SPEAKER_01"
    assert len(result.speakers) == 2
