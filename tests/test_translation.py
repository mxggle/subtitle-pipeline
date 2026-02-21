"""Tests for translate_chunk, translate_stream, and _chunk_list."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import _chunk_list, translate_chunk


# ---------------------------------------------------------------------------
# _chunk_list
# ---------------------------------------------------------------------------

class TestChunkList:
    def test_basic_chunking(self):
        lst = list(range(10))
        chunks = list(_chunk_list(lst, 3))
        assert len(chunks) == 4
        assert chunks[0] == [0, 1, 2]
        assert chunks[3] == [9]

    def test_exact_fit(self):
        chunks = list(_chunk_list([1, 2, 3, 4], 2))
        assert chunks == [[1, 2], [3, 4]]


# ---------------------------------------------------------------------------
# translate_chunk
# ---------------------------------------------------------------------------

def _make_mock_client(content: str):
    """Build a mock OpenAI client returning the given content."""
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


CHUNK = [
    {"start": "0", "end": "1", "text": "Hello", "index": 1},
    {"start": "1", "end": "2", "text": "World", "index": 2},
]


class TestTranslateChunkJson:
    """translate_chunk now expects a JSON array response."""

    @patch("pipeline.OpenAI", new=MagicMock())
    def test_valid_json_array(self):
        client = _make_mock_client(json.dumps(["Hola", "Mundo"]))
        result = translate_chunk(client, CHUNK, "Spanish", "gpt-4o-mini")
        assert result == ["Hola", "Mundo"]
        client.chat.completions.create.assert_called_once()

    @patch("pipeline.OpenAI", new=MagicMock())
    def test_json_with_markdown_fences(self):
        """```json ... ``` wrappers are stripped before parsing."""
        client = _make_mock_client('```json\n["Bonjour", "Monde"]\n```')
        result = translate_chunk(client, CHUNK, "French", "gpt-4o-mini")
        assert result == ["Bonjour", "Monde"]

    @patch("pipeline.OpenAI", new=MagicMock())
    def test_json_with_plain_fences(self):
        """``` ... ``` wrappers (no json tag) are stripped."""
        client = _make_mock_client('```\n["Hallo", "Welt"]\n```')
        result = translate_chunk(client, CHUNK, "German", "gpt-4o-mini")
        assert result == ["Hallo", "Welt"]


class TestTranslateChunkFallback:
    """When the LLM doesn't return valid JSON, fallback to line-by-line."""

    @patch("pipeline.OpenAI", new=MagicMock())
    def test_line_by_line_fallback(self):
        client = _make_mock_client("Translated Line 1\nTranslated Line 2")
        result = translate_chunk(client, CHUNK, "French", "gpt-4o-mini")
        assert len(result) == 2
        assert result[0] == "Translated Line 1"
        assert result[1] == "Translated Line 2"


class TestTranslateChunkLengthMismatch:
    """When LLM returns wrong number of items, padding occurs."""

    @patch("pipeline.OpenAI", new=MagicMock())
    def test_too_few_items_padded(self):
        """If LLM returns fewer items than expected, empty strings are appended."""
        client = _make_mock_client(json.dumps(["Only one"]))
        result = translate_chunk(client, CHUNK, "German", "gpt-4o-mini")
        assert len(result) == 2
        assert result[0] == "Only one"
        assert result[1] == ""

    @patch("pipeline.OpenAI", new=MagicMock())
    def test_too_many_items_truncated(self):
        """If LLM returns more items, extras are dropped."""
        client = _make_mock_client(json.dumps(["A", "B", "C", "D"]))
        result = translate_chunk(client, CHUNK, "German", "gpt-4o-mini")
        assert len(result) == 2
        assert result == ["A", "B"]


class TestTranslateChunkApiError:
    """Real API errors are re-raised."""

    @patch("pipeline.OpenAI", new=MagicMock())
    def test_api_exception_propagates(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ConnectionError("network error")
        with pytest.raises(ConnectionError, match="network error"):
            translate_chunk(mock_client, CHUNK, "Spanish", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# translate_stream (integration-level with mocks)
# ---------------------------------------------------------------------------

from pipeline import translate_stream

SAMPLE_SRT = (
    "1\n"
    "00:00:01,000 --> 00:00:03,000\n"
    "Hello world\n"
    "\n"
    "2\n"
    "00:00:05,000 --> 00:00:07,000\n"
    "Goodbye\n"
    "\n"
)


class TestTranslateStream:
    @patch("pipeline.OpenAI", new=MagicMock())
    @patch("pipeline.translate_chunk", return_value=["你好世界", "再见"])
    def test_full_srt_flow(self, mock_chunk, tmp_path):
        """translate_stream reads SRT, calls translate_chunk, writes output."""
        input_srt = tmp_path / "movie.eng.srt"
        input_srt.write_text(SAMPLE_SRT)

        # Mock OpenAI constructor
        with patch("pipeline.os.environ.get", return_value="sk-test"):
            ret = translate_stream(
                input_srt, output_path=None,
                target_language="Chinese", api_key="sk-test"
            )
        assert ret == 0
        output = tmp_path / "movie.eng.chinese.srt"
        assert output.exists()
        content = output.read_text()
        assert "你好世界" in content
        assert "再见" in content

    def test_no_openai_returns_1(self, capsys):
        """Without openai installed, returns 1."""
        with patch("pipeline.OpenAI", None):
            ret = translate_stream(
                Path("/movies/movie.srt"), output_path=None,
                target_language="Chinese"
            )
        assert ret == 1
        assert "openai" in capsys.readouterr().err

    @patch("pipeline.OpenAI", new=MagicMock())
    def test_no_api_key_returns_1(self, capsys):
        """Without API key, returns 1."""
        with patch("pipeline.os.environ.get", return_value=None), \
             patch("pipeline.load_dotenv", None):
            ret = translate_stream(
                Path("/movies/movie.srt"), output_path=None,
                target_language="Chinese", api_key=None
            )
        assert ret == 1
        assert "API key" in capsys.readouterr().err

    @patch("pipeline.OpenAI", new=MagicMock())
    @patch("pipeline.translate_chunk", return_value=["你好世界", "再见"])
    def test_custom_output_path(self, mock_chunk, tmp_path):
        input_srt = tmp_path / "movie.srt"
        input_srt.write_text(SAMPLE_SRT)
        custom_out = tmp_path / "custom.srt"

        with patch("pipeline.os.environ.get", return_value="sk-test"):
            ret = translate_stream(
                input_srt, output_path=custom_out,
                target_language="Chinese", api_key="sk-test"
            )
        assert ret == 0
        assert custom_out.exists()

    @patch("pipeline.OpenAI", new=MagicMock())
    @patch("pipeline.translate_chunk", return_value=[])
    def test_empty_srt_returns_1(self, mock_chunk, tmp_path, capsys):
        """Empty SRT content returns 1."""
        input_srt = tmp_path / "empty.srt"
        input_srt.write_text("")

        with patch("pipeline.os.environ.get", return_value="sk-test"):
            ret = translate_stream(
                input_srt, output_path=None,
                target_language="Chinese", api_key="sk-test"
            )
        assert ret == 1
        assert "No subtitle entries" in capsys.readouterr().err
