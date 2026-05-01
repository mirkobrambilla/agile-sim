"""Tests for OpenRouter client with mocked HTTP."""

from unittest.mock import MagicMock, patch

import pytest

from openrouter import OpenRouterClient, BASE_URL


def _mock_response(content: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ],
        "model": "test-model",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_chat_text_returns_content():
    client = OpenRouterClient(api_key="sk-test")

    mock_resp = MagicMock()
    mock_resp.json.return_value = _mock_response("Hello there!")
    mock_resp.raise_for_status = MagicMock()

    with patch("openrouter.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = client.chat_text(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
        )

    text, usage = result
    assert text == "Hello there!"
    assert usage["input_tokens"] == 10
    assert usage["output_tokens"] == 5
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == f"{BASE_URL}/chat/completions"
    payload = call_args[1]["json"]
    assert payload["model"] == "openai/gpt-4o-mini"
    assert payload["messages"] == [{"role": "user", "content": "hi"}]


def test_chat_sends_auth_header():
    client = OpenRouterClient(api_key="sk-my-key")

    mock_resp = MagicMock()
    mock_resp.json.return_value = _mock_response("ok")
    mock_resp.raise_for_status = MagicMock()

    with patch("openrouter.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        client.chat_text(
            model="test",
            messages=[{"role": "user", "content": "hi"}],
        )

    headers = mock_client.post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer sk-my-key"


def test_chat_raises_on_http_error():
    client = OpenRouterClient(api_key="sk-test")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("500 Server Error")

    with patch("openrouter.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(Exception, match="500"):
            client.chat_text(
                model="test",
                messages=[{"role": "user", "content": "hi"}],
            )
