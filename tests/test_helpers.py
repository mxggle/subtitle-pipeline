"""Tests for helper functions: _require_bin, _run, _chunk_list."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import _chunk_list, _require_bin, _run


# ---------------------------------------------------------------------------
# _require_bin
# ---------------------------------------------------------------------------

class TestRequireBin:
    def test_existing_binary(self):
        """No error when the binary exists on PATH."""
        with patch("shutil.which", return_value="/usr/bin/echo"):
            _require_bin("echo")  # should not raise

    def test_missing_binary(self, capsys):
        """sys.exit(2) when the binary is missing."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(SystemExit) as exc:
                _require_bin("nonexistent_tool")
            assert exc.value.code == 2
        captured = capsys.readouterr()
        assert "nonexistent_tool" in captured.err


# ---------------------------------------------------------------------------
# _run
# ---------------------------------------------------------------------------

class TestRun:
    def test_basic_execution(self):
        """_run should call subprocess.run and return the CompletedProcess."""
        fake = subprocess.CompletedProcess(
            args=["echo", "hi"], returncode=0, stdout="hi\n", stderr=""
        )
        with patch("subprocess.run", return_value=fake) as mock:
            result = _run(["echo", "hi"])
            assert result.returncode == 0
            assert result.stdout == "hi\n"
            mock.assert_called_once_with(
                ["echo", "hi"], capture_output=True, text=True, encoding="utf-8"
            )

    def test_verbose_stderr_forwarded(self, capsys):
        """When _verbose is True, stderr is printed."""
        import pipeline

        fake = subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr="debug info\n"
        )
        original = pipeline._verbose
        try:
            pipeline._verbose = True
            with patch("subprocess.run", return_value=fake):
                _run(["cmd"])
            captured = capsys.readouterr()
            assert "debug info" in captured.err
        finally:
            pipeline._verbose = original

    def test_quiet_stderr_not_forwarded(self, capsys):
        """When _verbose is False, stderr is NOT printed."""
        import pipeline

        fake = subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr="debug info\n"
        )
        original = pipeline._verbose
        try:
            pipeline._verbose = False
            with patch("subprocess.run", return_value=fake):
                _run(["cmd"])
            captured = capsys.readouterr()
            assert "debug info" not in captured.err
        finally:
            pipeline._verbose = original


# ---------------------------------------------------------------------------
# _chunk_list
# ---------------------------------------------------------------------------

class TestChunkList:
    def test_even_split(self):
        chunks = list(_chunk_list([1, 2, 3, 4], 2))
        assert chunks == [[1, 2], [3, 4]]

    def test_uneven_split(self):
        chunks = list(_chunk_list(list(range(10)), 3))
        assert len(chunks) == 4
        assert chunks[0] == [0, 1, 2]
        assert chunks[3] == [9]

    def test_single_chunk(self):
        chunks = list(_chunk_list([1, 2, 3], 10))
        assert chunks == [[1, 2, 3]]

    def test_empty_list(self):
        chunks = list(_chunk_list([], 5))
        assert chunks == []

    def test_chunk_size_one(self):
        chunks = list(_chunk_list([1, 2, 3], 1))
        assert chunks == [[1], [2], [3]]
