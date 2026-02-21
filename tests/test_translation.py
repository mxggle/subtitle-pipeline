import pytest
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

# Load the learning_lab.py script directly since "scripts" conflicts with a global module
script_path = Path(__file__).parent.parent / "scripts" / "learning_lab.py"
spec = importlib.util.spec_from_file_location("learning_lab", str(script_path))
learning_lab = importlib.util.module_from_spec(spec)
sys.modules["learning_lab"] = learning_lab
spec.loader.exec_module(learning_lab)

def test_chunk_list():
    lst = list(range(10))
    chunks = list(learning_lab._chunk_list(lst, 3))
    assert len(chunks) == 4
    assert chunks[0] == [0, 1, 2]
    assert chunks[3] == [9]

@patch("learning_lab.OpenAI", new=MagicMock())
def test_translate_chunk_basic():
    # Mocking openai client
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Mock returning 2 blocks separated by |||
    mock_message = MagicMock()
    mock_message.content = "Translated 1\n|||\nTranslated 2"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    chunk = [
        {"start": "0", "end": "1", "text": "Hello", "index": 1},
        {"start": "1", "end": "2", "text": "World", "index": 2}
    ]

    result = learning_lab.translate_chunk(mock_client, chunk, "Spanish", "gpt-4o-mini")
    assert len(result) == 2
    assert result[0] == "Translated 1"
    assert result[1] == "Translated 2"
    mock_client.chat.completions.create.assert_called_once()

@patch("learning_lab.OpenAI", new=MagicMock())
def test_translate_chunk_fallback():
    # If LLM doesn't output the delimiter properly, but returns exactly N lines
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Missing |||, but exactly two lines
    mock_message = MagicMock()
    mock_message.content = "Translated Line 1\nTranslated Line 2"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    chunk = [
        {"start": "0", "end": "1", "text": "Hello", "index": 1},
        {"start": "1", "end": "2", "text": "World", "index": 2}
    ]

    result = learning_lab.translate_chunk(mock_client, chunk, "French", "gpt-4o-mini")
    assert len(result) == 2
    assert result[0] == "Translated Line 1"
    assert result[1] == "Translated Line 2"

@patch("learning_lab.OpenAI", new=MagicMock())
def test_translate_chunk_failure():
    # If LLM returns wrong number of lines and no delimiters
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Just one line summary instead of translation"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    chunk = [
        {"start": "0", "end": "1", "text": "Hello", "index": 1},
        {"start": "1", "end": "2", "text": "World", "index": 2}
    ]

    with pytest.raises(ValueError, match="LLM translation alignment failed"):
        learning_lab.translate_chunk(mock_client, chunk, "German", "gpt-4o-mini")
