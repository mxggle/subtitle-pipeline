"""Tests for transcribe_stream with mocked Whisper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import transcribe_stream


def _fake_run(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["whisper"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestTranscribeStream:
    @patch("shutil.which", return_value=None)
    def test_whisper_not_found_returns_1(self, mock_which, capsys):
        ret = transcribe_stream(Path("/movies/movie.mp4"), output_path=None)
        assert ret == 1
        assert "whisper" in capsys.readouterr().err

    @patch("pipeline._run")
    @patch("shutil.which", return_value="/usr/local/bin/whisper")
    def test_successful_transcription(self, mock_which, mock_run, tmp_path, capsys):
        """Whisper generates an SRT at the expected location."""
        input_path = tmp_path / "movie.mp4"
        input_path.touch()
        # Whisper creates <stem>.srt in the output dir
        expected_out = tmp_path / "movie.srt"
        expected_out.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n")

        mock_run.return_value = _fake_run()
        ret = transcribe_stream(input_path, output_path=None)
        assert ret == 0
        output = capsys.readouterr().out
        assert "Transcription complete" in output

    @patch("pipeline._run")
    @patch("shutil.which", return_value="/usr/local/bin/whisper")
    def test_custom_output_path_renames(self, mock_which, mock_run, tmp_path, capsys):
        """When output_path differs from expected, file is moved."""
        input_path = tmp_path / "movie.mp4"
        input_path.touch()
        expected_out = tmp_path / "movie.srt"
        expected_out.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n")

        custom_output = tmp_path / "custom_name.srt"
        mock_run.return_value = _fake_run()
        ret = transcribe_stream(input_path, output_path=custom_output)
        assert ret == 0
        assert custom_output.exists()
        assert not expected_out.exists()  # was moved

    @patch("pipeline._run")
    @patch("shutil.which", return_value="/usr/local/bin/whisper")
    def test_language_flag_passed(self, mock_which, mock_run, tmp_path, capsys):
        """--language flag is forwarded to whisper command."""
        input_path = tmp_path / "movie.mp4"
        input_path.touch()
        expected_out = tmp_path / "movie.srt"
        expected_out.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n")

        mock_run.return_value = _fake_run()
        transcribe_stream(input_path, output_path=None, language="en")
        call_args = mock_run.call_args[0][0]
        assert "--language" in call_args
        assert "en" in call_args

    @patch("pipeline._run")
    @patch("shutil.which", return_value="/usr/local/bin/whisper")
    def test_model_flag_passed(self, mock_which, mock_run, tmp_path, capsys):
        """--model flag is forwarded to whisper command."""
        input_path = tmp_path / "movie.mp4"
        input_path.touch()
        expected_out = tmp_path / "movie.srt"
        expected_out.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n")

        mock_run.return_value = _fake_run()
        transcribe_stream(input_path, output_path=None, model="large")
        call_args = mock_run.call_args[0][0]
        assert "--model" in call_args
        assert "large" in call_args

    @patch("pipeline._run")
    @patch("shutil.which", return_value="/usr/local/bin/whisper")
    def test_whisper_failure_returns_code(self, mock_which, mock_run, capsys):
        ret = transcribe_stream(Path("/movies/movie.mp4"), output_path=None)
        mock_run.return_value = _fake_run(returncode=1, stderr="whisper crashed")
        # Need to call again with the failing mock
        ret = transcribe_stream(Path("/movies/movie.mp4"), output_path=None)
        assert ret == 1

    @patch("pipeline._run")
    @patch("shutil.which", return_value="/usr/local/bin/whisper")
    def test_whisper_output_not_found_warns(self, mock_which, mock_run, tmp_path, capsys):
        """If whisper succeeds but the expected output file doesn't exist, warn."""
        input_path = tmp_path / "movie.mp4"
        input_path.touch()
        # Don't create the expected output
        mock_run.return_value = _fake_run()
        ret = transcribe_stream(input_path, output_path=None)
        assert ret == 0
        assert "not found" in capsys.readouterr().err
