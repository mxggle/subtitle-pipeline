"""Tests for merge_streams orchestrator with mocked ffmpeg."""

from __future__ import annotations

import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import merge_streams, _parse_srt_time as _t


SAMPLE_STREAMS = [
    {"subtitle_index": 0, "global_index": 2, "codec": "subrip", "language": "eng", "title": "English"},
    {"subtitle_index": 1, "global_index": 3, "codec": "subrip", "language": "chi", "title": "Chinese"},
    {"subtitle_index": 2, "global_index": 4, "codec": "subrip", "language": "jpn", "title": "Japanese"},
]

ENGLISH_SRT = (
    "1\n"
    "00:00:01,000 --> 00:00:03,000\n"
    "Hello world\n"
    "\n"
    "2\n"
    "00:00:05,000 --> 00:00:07,000\n"
    "Goodbye\n"
    "\n"
)

CHINESE_SRT = (
    "1\n"
    "00:00:01,100 --> 00:00:02,900\n"
    "你好世界\n"
    "\n"
    "2\n"
    "00:00:05,100 --> 00:00:06,900\n"
    "再见\n"
    "\n"
)

JAPANESE_SRT = (
    "1\n"
    "00:00:01,050 --> 00:00:02,950\n"
    "こんにちは世界\n"
    "\n"
)


def _fake_run_for_stream(stream_idx):
    """Return appropriate SRT based on stream index."""
    content_map = {
        "0:s:0": ENGLISH_SRT,
        "0:s:1": CHINESE_SRT,
        "0:s:2": JAPANESE_SRT,
    }

    def side_effect(cmd):
        for key, content in content_map.items():
            if key in cmd:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout=content, stderr=""
                )
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="stream not found")

    return side_effect


class TestMergeStreams:
    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_merge_by_languages(self, mock_probe, mock_run, tmp_path):
        mock_run.side_effect = _fake_run_for_stream(None)
        output = tmp_path / "merged.srt"
        ret = merge_streams(
            Path("/movies/movie.mkv"), output_path=output,
            indices=None, languages=["eng", "chi"]
        )
        assert ret == 0
        assert output.exists()
        content = output.read_text()
        assert "Hello world" in content
        assert "你好世界" in content

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_merge_by_indices(self, mock_probe, mock_run, tmp_path):
        mock_run.side_effect = _fake_run_for_stream(None)
        output = tmp_path / "merged.srt"
        ret = merge_streams(
            Path("/movies/movie.mkv"), output_path=output,
            indices=[0, 1], languages=None
        )
        assert ret == 0
        content = output.read_text()
        assert "Hello world" in content
        assert "你好世界" in content

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_merge_default_first_two(self, mock_probe, mock_run, tmp_path):
        mock_run.side_effect = _fake_run_for_stream(None)
        output = tmp_path / "merged.srt"
        ret = merge_streams(
            Path("/movies/movie.mkv"), output_path=output,
            indices=None, languages=None
        )
        assert ret == 0
        content = output.read_text()
        assert "Hello world" in content
        assert "你好世界" in content

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_merge_three_streams(self, mock_probe, mock_run, tmp_path):
        mock_run.side_effect = _fake_run_for_stream(None)
        output = tmp_path / "merged.srt"
        ret = merge_streams(
            Path("/movies/movie.mkv"), output_path=output,
            indices=[0, 1, 2], languages=None
        )
        assert ret == 0
        content = output.read_text()
        assert "Hello world" in content
        assert "你好世界" in content
        assert "こんにちは世界" in content

    @patch("pipeline.probe_subtitle_streams", return_value=[])
    def test_no_streams_returns_1(self, mock_probe, capsys):
        ret = merge_streams(
            Path("/movies/movie.mkv"), output_path=None,
            indices=None, languages=None
        )
        assert ret == 1
        assert "No subtitle streams found" in capsys.readouterr().err

    @patch("pipeline.probe_subtitle_streams", return_value=[SAMPLE_STREAMS[0]])
    def test_only_one_stream_returns_1(self, mock_probe, capsys):
        """Cannot merge with fewer than 2 streams."""
        ret = merge_streams(
            Path("/movies/movie.mkv"), output_path=None,
            indices=None, languages=None
        )
        assert ret == 1
        assert "Need at least 2 streams" in capsys.readouterr().err

    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_invalid_index_returns_1(self, mock_probe, capsys):
        ret = merge_streams(
            Path("/movies/movie.mkv"), output_path=None,
            indices=[0, 99], languages=None
        )
        assert ret == 1
        assert "No subtitle stream at index 99" in capsys.readouterr().err

    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_invalid_language_returns_1(self, mock_probe, capsys):
        ret = merge_streams(
            Path("/movies/movie.mkv"), output_path=None,
            indices=None, languages=["eng", "kor"]
        )
        assert ret == 1
        assert "No subtitle stream with language=kor" in capsys.readouterr().err

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_default_output_path_format(self, mock_probe, mock_run, tmp_path):
        """When output_path is None, the file is named with languages."""
        mock_run.side_effect = _fake_run_for_stream(None)
        # Use a path in tmp_path to ensure the default path is writable
        input_path = tmp_path / "movie.mkv"
        input_path.touch()
        ret = merge_streams(
            input_path, output_path=None,
            indices=None, languages=["eng", "chi"]
        )
        assert ret == 0
        expected = tmp_path / "movie.eng-chi.merged.srt"
        assert expected.exists()

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_merged_entries_sorted_by_time(self, mock_probe, mock_run, tmp_path):
        """Merged SRT entries should be sorted by start time."""
        mock_run.side_effect = _fake_run_for_stream(None)
        output = tmp_path / "merged.srt"
        merge_streams(
            Path("/movies/movie.mkv"), output_path=output,
            indices=[0, 1], languages=None
        )
        content = output.read_text()
        # First entry should start at 00:00:01
        assert content.index("00:00:01") < content.index("00:00:05")

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_ffmpeg_failure_during_extraction(self, mock_probe, mock_run, capsys):
        """If ffmpeg fails extracting a stream, merge_streams returns error."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ffmpeg"], returncode=1, stdout="", stderr="extraction failed"
        )
        ret = merge_streams(
            Path("/movies/movie.mkv"), output_path=None,
            indices=[0, 1], languages=None
        )
        assert ret == 1
