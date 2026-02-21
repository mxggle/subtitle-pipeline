"""Tests for the main() CLI argument parsing and dispatch."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pipeline


# Always stub out _require_bin so tests don't need ffmpeg/ffprobe installed.
@pytest.fixture(autouse=True)
def stub_require_bin():
    with patch("pipeline._require_bin"):
        yield


class TestMainList:
    @patch("pipeline.list_streams", return_value=0)
    def test_list_dispatches(self, mock_list):
        with patch("sys.argv", ["pipeline.py", "list", "/movies/movie.mkv"]):
            ret = pipeline.main()
        assert ret == 0
        mock_list.assert_called_once()
        assert mock_list.call_args[0][0] == Path("/movies/movie.mkv")


class TestMainExtract:
    @patch("pipeline.extract_stream", return_value=0)
    def test_extract_dispatches(self, mock_extract):
        with patch("sys.argv", ["pipeline.py", "extract", "/movies/movie.mkv", "--index", "1", "--to-srt"]):
            ret = pipeline.main()
        assert ret == 0
        mock_extract.assert_called_once()

    @patch("pipeline.extract_stream", return_value=0)
    def test_extract_by_language(self, mock_extract):
        with patch("sys.argv", ["pipeline.py", "extract", "/movies/movie.mkv", "--language", "eng"]):
            ret = pipeline.main()
        assert ret == 0

    def test_extract_index_and_language_errors(self, capsys):
        with patch("sys.argv", ["pipeline.py", "extract", "/movies/movie.mkv", "--index", "0", "--language", "eng"]):
            ret = pipeline.main()
        assert ret == 2
        assert "not both" in capsys.readouterr().err


class TestMainMerge:
    @patch("pipeline.merge_streams", return_value=0)
    def test_merge_dispatches(self, mock_merge):
        with patch("sys.argv", ["pipeline.py", "merge", "/movies/movie.mkv", "--languages", "eng", "chi"]):
            ret = pipeline.main()
        assert ret == 0
        mock_merge.assert_called_once()

    def test_merge_indices_and_languages_errors(self, capsys):
        with patch("sys.argv", ["pipeline.py", "merge", "/movies/movie.mkv", "--indices", "0", "1", "--languages", "eng", "chi"]):
            ret = pipeline.main()
        assert ret == 2
        assert "not both" in capsys.readouterr().err


class TestMainTranslate:
    @patch("pipeline.translate_stream", return_value=0)
    def test_translate_dispatches(self, mock_translate):
        with patch("sys.argv", ["pipeline.py", "translate", "/movies/movie.srt", "--target-language", "Chinese"]):
            ret = pipeline.main()
        assert ret == 0
        mock_translate.assert_called_once()

    @patch("pipeline.translate_stream", return_value=0)
    def test_translate_with_all_flags(self, mock_translate):
        with patch("sys.argv", [
            "pipeline.py", "translate", "/movies/movie.srt",
            "--target-language", "Chinese",
            "--api-key", "sk-test",
            "--base-url", "https://api.example.com",
            "--model", "deepseek-chat",
        ]):
            ret = pipeline.main()
        assert ret == 0


class TestMainTranscribe:
    @patch("pipeline.transcribe_stream", return_value=0)
    def test_transcribe_dispatches(self, mock_transcribe):
        with patch("sys.argv", ["pipeline.py", "transcribe", "/movies/movie.mp4"]):
            ret = pipeline.main()
        assert ret == 0
        mock_transcribe.assert_called_once()

    @patch("pipeline.transcribe_stream", return_value=0)
    def test_transcribe_with_options(self, mock_transcribe):
        with patch("sys.argv", [
            "pipeline.py", "transcribe", "/movies/movie.mp4",
            "--model", "large",
            "--language", "en",
        ]):
            ret = pipeline.main()
        assert ret == 0


class TestMainVerbosity:
    @patch("pipeline.list_streams", return_value=0)
    def test_verbose_flag_sets_module_var(self, mock_list):
        with patch("sys.argv", ["pipeline.py", "--verbose", "list", "/movies/movie.mkv"]):
            pipeline.main()
        assert pipeline._verbose is True
        # Reset
        pipeline._verbose = False

    @patch("pipeline.list_streams", return_value=0)
    def test_quiet_flag(self, mock_list):
        """--quiet is accepted without error."""
        with patch("sys.argv", ["pipeline.py", "--quiet", "list", "/movies/movie.mkv"]):
            ret = pipeline.main()
        assert ret == 0
