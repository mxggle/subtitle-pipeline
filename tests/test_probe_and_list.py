"""Tests for probe_subtitle_streams and list_streams."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import list_streams, probe_subtitle_streams

# ---------------------------------------------------------------------------
# Sample ffprobe JSON payloads
# ---------------------------------------------------------------------------

FFPROBE_TWO_STREAMS = json.dumps({
    "streams": [
        {
            "index": 2,
            "codec_name": "subrip",
            "tags": {"language": "eng", "title": "English"},
        },
        {
            "index": 3,
            "codec_name": "ass",
            "tags": {"language": "jpn", "title": "Japanese"},
        },
    ]
})

FFPROBE_NO_STREAMS = json.dumps({"streams": []})

FFPROBE_MISSING_TAGS = json.dumps({
    "streams": [
        {
            "index": 5,
            "codec_name": "subrip",
            # no tags at all
        },
    ]
})


def _fake_run(stdout="", stderr="", returncode=0):
    """Return a fake CompletedProcess for _run mocking."""
    return subprocess.CompletedProcess(
        args=["ffprobe"], returncode=returncode, stdout=stdout, stderr=stderr
    )


# ---------------------------------------------------------------------------
# probe_subtitle_streams
# ---------------------------------------------------------------------------

class TestProbeSubtitleStreams:
    @patch("pipeline._run")
    def test_two_streams_parsed(self, mock_run):
        mock_run.return_value = _fake_run(stdout=FFPROBE_TWO_STREAMS)
        streams = probe_subtitle_streams(Path("movie.mkv"))
        assert len(streams) == 2

        assert streams[0]["subtitle_index"] == 0
        assert streams[0]["global_index"] == 2
        assert streams[0]["codec"] == "subrip"
        assert streams[0]["language"] == "eng"
        assert streams[0]["title"] == "English"

        assert streams[1]["subtitle_index"] == 1
        assert streams[1]["language"] == "jpn"
        assert streams[1]["codec"] == "ass"

    @patch("pipeline._run")
    def test_no_streams(self, mock_run):
        mock_run.return_value = _fake_run(stdout=FFPROBE_NO_STREAMS)
        streams = probe_subtitle_streams(Path("movie.mkv"))
        assert streams == []

    @patch("pipeline._run")
    def test_missing_tags_uses_defaults(self, mock_run):
        mock_run.return_value = _fake_run(stdout=FFPROBE_MISSING_TAGS)
        streams = probe_subtitle_streams(Path("movie.mkv"))
        assert len(streams) == 1
        assert streams[0]["language"] == "und"
        assert streams[0]["title"] == ""

    @patch("pipeline._run")
    def test_ffprobe_failure_exits(self, mock_run):
        mock_run.return_value = _fake_run(returncode=1, stderr="ffprobe error")
        with pytest.raises(SystemExit) as exc:
            probe_subtitle_streams(Path("bad.mkv"))
        assert exc.value.code == 1

    @patch("pipeline._run")
    def test_empty_stdout_returns_empty(self, mock_run):
        mock_run.return_value = _fake_run(stdout="{}")
        streams = probe_subtitle_streams(Path("movie.mkv"))
        assert streams == []


# ---------------------------------------------------------------------------
# list_streams
# ---------------------------------------------------------------------------

class TestListStreams:
    @patch("pipeline.probe_subtitle_streams")
    def test_prints_table(self, mock_probe, capsys):
        mock_probe.return_value = [
            {"subtitle_index": 0, "global_index": 2, "codec": "subrip", "language": "eng", "title": "English"},
        ]
        ret = list_streams(Path("movie.mkv"))
        assert ret == 0
        output = capsys.readouterr().out
        assert "subtitle_index" in output  # header
        assert "eng" in output
        assert "subrip" in output

    @patch("pipeline.probe_subtitle_streams")
    def test_no_streams_returns_1(self, mock_probe, capsys):
        mock_probe.return_value = []
        ret = list_streams(Path("movie.mkv"))
        assert ret == 1
        output = capsys.readouterr().out
        assert "No subtitle streams found" in output

    @patch("pipeline.probe_subtitle_streams")
    def test_multiple_streams(self, mock_probe, capsys):
        mock_probe.return_value = [
            {"subtitle_index": 0, "global_index": 2, "codec": "subrip", "language": "eng", "title": ""},
            {"subtitle_index": 1, "global_index": 3, "codec": "ass", "language": "jpn", "title": "日本語"},
        ]
        ret = list_streams(Path("movie.mkv"))
        assert ret == 0
        output = capsys.readouterr().out
        lines = output.strip().split("\n")
        assert len(lines) == 3  # header + 2 streams
