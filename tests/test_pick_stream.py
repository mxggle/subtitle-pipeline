"""Tests for pick_stream – stream selection by index, language, or default."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import pick_stream

SAMPLE_STREAMS = [
    {"subtitle_index": 0, "global_index": 2, "codec": "subrip", "language": "eng", "title": "English"},
    {"subtitle_index": 1, "global_index": 3, "codec": "subrip", "language": "chi", "title": "Chinese"},
    {"subtitle_index": 2, "global_index": 4, "codec": "ass",    "language": "jpn", "title": "Japanese"},
]


class TestPickStreamByIndex:
    def test_found(self):
        s = pick_stream(SAMPLE_STREAMS, index=1, language=None)
        assert s["language"] == "chi"

    def test_not_found(self):
        with pytest.raises(ValueError, match="No subtitle stream at index 99"):
            pick_stream(SAMPLE_STREAMS, index=99, language=None)

    def test_index_zero(self):
        s = pick_stream(SAMPLE_STREAMS, index=0, language=None)
        assert s["language"] == "eng"


class TestPickStreamByLanguage:
    def test_found(self):
        s = pick_stream(SAMPLE_STREAMS, index=None, language="jpn")
        assert s["subtitle_index"] == 2

    def test_case_insensitive(self):
        s = pick_stream(SAMPLE_STREAMS, index=None, language="ENG")
        assert s["language"] == "eng"

    def test_not_found(self):
        with pytest.raises(ValueError, match="No subtitle stream with language=kor"):
            pick_stream(SAMPLE_STREAMS, index=None, language="kor")


class TestPickStreamDefault:
    def test_returns_first(self):
        s = pick_stream(SAMPLE_STREAMS, index=None, language=None)
        assert s["subtitle_index"] == 0

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="No subtitle streams found"):
            pick_stream([], index=None, language=None)


class TestPickStreamPriority:
    def test_index_takes_precedence_over_language(self):
        """When both index and language are given, index wins (language is ignored)."""
        s = pick_stream(SAMPLE_STREAMS, index=2, language="eng")
        assert s["language"] == "jpn"  # index=2 is Japanese
