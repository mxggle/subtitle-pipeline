"""Tests for extract_stream – subtitle extraction with mocked ffmpeg."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import extract_stream


def _fake_run(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["ffmpeg"], returncode=returncode, stdout=stdout, stderr=stderr
    )


SAMPLE_STREAMS = [
    {"subtitle_index": 0, "global_index": 2, "codec": "subrip", "language": "eng", "title": "English"},
    {"subtitle_index": 1, "global_index": 3, "codec": "ass", "language": "jpn", "title": "Japanese"},
]


class TestExtractStream:
    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_extract_default_first_stream(self, mock_probe, mock_run, capsys):
        mock_run.return_value = _fake_run()
        ret = extract_stream(
            Path("/movies/movie.mkv"), output_path=None,
            index=None, language=None, to_srt=False
        )
        assert ret == 0
        # Check ffmpeg was called with correct map spec
        call_args = mock_run.call_args[0][0]
        assert "-map" in call_args
        map_idx = call_args.index("-map")
        assert call_args[map_idx + 1] == "0:s:0"
        output = capsys.readouterr().out
        assert "Extracted" in output

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_extract_by_language(self, mock_probe, mock_run, capsys):
        mock_run.return_value = _fake_run()
        ret = extract_stream(
            Path("/movies/movie.mkv"), output_path=None,
            index=None, language="jpn", to_srt=False
        )
        assert ret == 0
        call_args = mock_run.call_args[0][0]
        map_idx = call_args.index("-map")
        assert call_args[map_idx + 1] == "0:s:1"

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_extract_to_srt_adds_codec_flag(self, mock_probe, mock_run, capsys):
        mock_run.return_value = _fake_run()
        extract_stream(
            Path("/movies/movie.mkv"), output_path=None,
            index=0, language=None, to_srt=True
        )
        call_args = mock_run.call_args[0][0]
        assert "-c:s" in call_args
        cs_idx = call_args.index("-c:s")
        assert call_args[cs_idx + 1] == "srt"

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_extract_copy_codec_when_not_to_srt(self, mock_probe, mock_run, capsys):
        mock_run.return_value = _fake_run()
        extract_stream(
            Path("/movies/movie.mkv"), output_path=None,
            index=0, language=None, to_srt=False
        )
        call_args = mock_run.call_args[0][0]
        cs_idx = call_args.index("-c:s")
        assert call_args[cs_idx + 1] == "copy"

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_custom_output_path(self, mock_probe, mock_run, capsys):
        custom_path = Path("/tmp/output.srt")
        mock_run.return_value = _fake_run()
        extract_stream(
            Path("/movies/movie.mkv"), output_path=custom_path,
            index=0, language=None, to_srt=True
        )
        call_args = mock_run.call_args[0][0]
        assert str(custom_path) in call_args

    @patch("pipeline.probe_subtitle_streams", return_value=[])
    def test_no_streams_returns_1(self, mock_probe, capsys):
        ret = extract_stream(
            Path("/movies/movie.mkv"), output_path=None,
            index=None, language=None, to_srt=False
        )
        assert ret == 1
        assert "No subtitle streams found" in capsys.readouterr().err

    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_invalid_index_returns_1(self, mock_probe, capsys):
        ret = extract_stream(
            Path("/movies/movie.mkv"), output_path=None,
            index=99, language=None, to_srt=False
        )
        assert ret == 1
        assert "No subtitle stream at index 99" in capsys.readouterr().err

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_ffmpeg_failure_returns_code(self, mock_probe, mock_run, capsys):
        mock_run.return_value = _fake_run(returncode=1, stderr="ffmpeg exploded")
        ret = extract_stream(
            Path("/movies/movie.mkv"), output_path=None,
            index=0, language=None, to_srt=False
        )
        assert ret == 1
        assert "ffmpeg exploded" in capsys.readouterr().err

    @patch("pipeline._run")
    @patch("pipeline.probe_subtitle_streams", return_value=SAMPLE_STREAMS)
    def test_default_output_path_format(self, mock_probe, mock_run, capsys):
        """Default output includes language and extension from codec."""
        mock_run.return_value = _fake_run()
        extract_stream(
            Path("/movies/movie.mkv"), output_path=None,
            index=0, language=None, to_srt=False
        )
        call_args = mock_run.call_args[0][0]
        output_arg = call_args[-1]
        assert "eng" in output_arg
        assert output_arg.endswith(".srt")  # subrip -> srt
