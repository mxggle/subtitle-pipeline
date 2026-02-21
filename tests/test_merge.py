"""Tests for the subtitle merge and SRT parsing logic in learning_lab.py."""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pytest

# Ensure the scripts directory is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from learning_lab import _format_srt_time, _parse_srt, _parse_srt_time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _t(time_str: str) -> timedelta:
    """Shortcut for _parse_srt_time in test data."""
    return _parse_srt_time(time_str)


# ---------------------------------------------------------------------------
# _parse_srt_time / _format_srt_time
# ---------------------------------------------------------------------------

class TestTimeConversion:
    def test_parse_basic(self):
        td = _parse_srt_time("01:02:03,456")
        assert td == timedelta(hours=1, minutes=2, seconds=3, milliseconds=456)

    def test_parse_zero(self):
        assert _parse_srt_time("00:00:00,000") == timedelta(0)

    def test_roundtrip(self):
        original = "00:05:12,340"
        assert _format_srt_time(_parse_srt_time(original)) == original

    def test_format(self):
        td = timedelta(hours=0, minutes=1, seconds=30, milliseconds=500)
        assert _format_srt_time(td) == "00:01:30,500"


# ---------------------------------------------------------------------------
# _parse_srt
# ---------------------------------------------------------------------------

SAMPLE_SRT_LF = (
    "1\n"
    "00:00:13,304 --> 00:00:15,849\n"
    "You might not remember him, but...\n"
    "\n"
    "2\n"
    "00:00:16,474 --> 00:00:18,309\n"
    "Stay there. I'm coming back.\n"
    "\n"
)

SAMPLE_SRT_CRLF = SAMPLE_SRT_LF.replace("\n", "\r\n")

SAMPLE_SRT_NO_TRAILING_NEWLINE = (
    "1\n"
    "00:00:13,304 --> 00:00:15,849\n"
    "You might not remember him, but..."
)


class TestParseSrt:
    def test_parse_lf(self):
        entries = _parse_srt(SAMPLE_SRT_LF)
        assert len(entries) == 2
        assert entries[0]["text"] == "You might not remember him, but..."
        assert entries[1]["text"] == "Stay there. I'm coming back."

    def test_parse_crlf(self):
        """CRLF line endings must not break parsing."""
        entries = _parse_srt(SAMPLE_SRT_CRLF)
        assert len(entries) == 2
        assert entries[0]["text"] == "You might not remember him, but..."

    def test_parse_no_trailing_newline(self):
        """The last entry must be captured even without a trailing blank line."""
        entries = _parse_srt(SAMPLE_SRT_NO_TRAILING_NEWLINE)
        assert len(entries) == 1
        assert entries[0]["text"] == "You might not remember him, but..."

    def test_parse_timedelta_values(self):
        entries = _parse_srt(SAMPLE_SRT_LF)
        assert entries[0]["start"] == _t("00:00:13,304")
        assert entries[0]["end"] == _t("00:00:15,849")

    def test_parse_empty_string(self):
        assert _parse_srt("") == []

    def test_multiline_subtitle_text(self):
        srt = (
            "1\n"
            "00:00:01,000 --> 00:00:03,000\n"
            "Line one\n"
            "Line two\n"
            "\n"
        )
        entries = _parse_srt(srt)
        assert len(entries) == 1
        assert entries[0]["text"] == "Line one\nLine two"


# ---------------------------------------------------------------------------
# Merge logic (unit-level, no ffmpeg needed)
# ---------------------------------------------------------------------------

# Re-implement the pure-Python merge core here so we can test it in
# isolation without needing an actual video file.  The constants are
# imported from the main module to ensure consistency.
from learning_lab import MIN_OVERLAP_RATIO, MIN_OVERLAP_SECONDS


def _merge_parsed(contents: list[list[dict]]) -> list[dict]:
    """Pure merge logic extracted for testing (mirrors merge_streams core)."""
    primary_entries = [
        {"start": e["start"], "end": e["end"], "texts": [e["text"]]}
        for e in contents[0]
    ]

    standalone_entries: list[dict] = []
    for stream_idx in range(1, len(contents)):
        for s_entry in contents[stream_idx]:
            overlaps: list[dict] = []
            s_len = (s_entry["end"] - s_entry["start"]).total_seconds()

            for p_entry in primary_entries:
                overlap_start = max(p_entry["start"], s_entry["start"])
                overlap_end = min(p_entry["end"], s_entry["end"])
                o_len = (overlap_end - overlap_start).total_seconds()
                if o_len > 0:
                    p_len = (p_entry["end"] - p_entry["start"]).total_seconds()
                    if o_len >= MIN_OVERLAP_SECONDS or o_len > MIN_OVERLAP_RATIO * min(s_len, p_len):
                        overlaps.append(p_entry)

            if not overlaps:
                standalone_entries.append(
                    {"start": s_entry["start"], "end": s_entry["end"], "texts": [s_entry["text"]]}
                )
            else:
                for p in overlaps:
                    if s_entry["text"] not in p["texts"]:
                        p["texts"].append(s_entry["text"])

    merged = [
        {"start": p["start"], "end": p["end"], "text": "\n".join(p["texts"])}
        for p in primary_entries
    ] + [
        {"start": s["start"], "end": s["end"], "text": "\n".join(s["texts"])}
        for s in standalone_entries
    ]
    merged.sort(key=lambda x: x["start"])
    return merged


class TestMerge:
    def test_overlapping_entries_are_merged(self):
        """Secondary entries that overlap a primary entry should be combined."""
        contents = [
            [
                {"start": _t("00:00:13,304"), "end": _t("00:00:15,849"), "text": "Hello world"},
            ],
            [
                {"start": _t("00:00:13,388"), "end": _t("00:00:15,849"), "text": "你好世界"},
            ],
        ]
        merged = _merge_parsed(contents)
        assert len(merged) == 1
        assert merged[0]["text"] == "Hello world\n你好世界"

    def test_non_overlapping_entries_kept_standalone(self):
        """Non-overlapping secondary entries remain standalone."""
        contents = [
            [
                {"start": _t("00:00:01,000"), "end": _t("00:00:03,000"), "text": "First"},
            ],
            [
                {"start": _t("00:00:10,000"), "end": _t("00:00:12,000"), "text": "独立条目"},
            ],
        ]
        merged = _merge_parsed(contents)
        assert len(merged) == 2
        assert merged[0]["text"] == "First"
        assert merged[1]["text"] == "独立条目"

    def test_duplicate_text_not_appended(self):
        """The same text should not be appended twice."""
        contents = [
            [
                {"start": _t("00:00:01,000"), "end": _t("00:00:03,000"), "text": "Same"},
            ],
            [
                {"start": _t("00:00:01,000"), "end": _t("00:00:03,000"), "text": "Same"},
            ],
        ]
        merged = _merge_parsed(contents)
        assert len(merged) == 1
        assert merged[0]["text"] == "Same"

    def test_sort_order(self):
        """Merged output must be sorted by start time."""
        contents = [
            [
                {"start": _t("00:00:05,000"), "end": _t("00:00:06,000"), "text": "B"},
                {"start": _t("00:00:01,000"), "end": _t("00:00:02,000"), "text": "A"},
            ],
            [
                {"start": _t("00:00:03,000"), "end": _t("00:00:04,000"), "text": "C"},
            ],
        ]
        merged = _merge_parsed(contents)
        texts = [m["text"] for m in merged]
        assert texts == ["A", "C", "B"]

    def test_three_way_merge(self):
        """Merge should work with more than two streams."""
        contents = [
            [{"start": _t("00:00:01,000"), "end": _t("00:00:03,000"), "text": "ENG"}],
            [{"start": _t("00:00:01,100"), "end": _t("00:00:02,900"), "text": "中文"}],
            [{"start": _t("00:00:01,050"), "end": _t("00:00:02,950"), "text": "日本語"}],
        ]
        merged = _merge_parsed(contents)
        assert len(merged) == 1
        assert "ENG" in merged[0]["text"]
        assert "中文" in merged[0]["text"]
        assert "日本語" in merged[0]["text"]
