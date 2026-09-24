import pytest
import requests

from ai_service_desk.engine.groq import GroqClient, GroqError


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data
        self.closed = False

    def json(self):
        return self._data

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, *, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []
        self.closed = False

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


def _ollama_payload():
    return {
        "model": "qwen3.5:4b",
        "think": False,
        "stream": False,
        "keep_alive": "30m",
        "messages": [
            {"role": "system", "content": "Return JSON."},
            {"role": "user", "content": "hello"},
        ],
        "format": {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        "options": {
            "temperature": 0.4,
            "num_ctx": 3072,
            "num_predict": 256,
        },
    }


def test_chat_adapts_only_supported_groq_fields():
    response = FakeResponse(
        data={
            "choices": [
                {
                    "message": {"role": "assistant", "content": '{"answer":"ok"}'},
                    "finish_reason": "stop",
                }
            ]
        }
    )
    session = FakeSession(response=response)
    client = GroqClient(api_key="test-key", model="openai/gpt-oss-120b")
    client.session = session

    client.chat(_ollama_payload())

    url, request = session.requests[0]
    assert url == "https://api.groq.com/openai/v1/chat/completions"
    assert request["json"] == {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": "Return JSON."},
            {"role": "user", "content": "hello"},
        ],
        "stream": False,
        "temperature": 0.4,
        "max_completion_tokens": 256,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "jup_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                    "additionalProperties": False,
                },
            },
        },
    }
    assert request["headers"] == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
    }
    assert request["timeout"] == (5, 180)
    assert request["allow_redirects"] is False
    assert response.closed


@pytest.mark.parametrize(
    ("finish_reason", "expected"),
    [("stop", "stop"), ("length", "length")],
)
def test_chat_normalizes_content_and_finish_reason(finish_reason, expected):
    session = FakeSession(
        response=FakeResponse(
            data={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": '{"answer":"ok"}'},
                        "finish_reason": finish_reason,
                    }
                ]
            }
        )
    )
    client = GroqClient(api_key="test-key")
    client.session = session

    result = client.chat(_ollama_payload())

    assert result == {
        "message": {"content": '{"answer":"ok"}'},
        "done_reason": expected,
    }


def test_missing_api_key_fails_before_creating_a_request(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        GroqClient()


def test_http_error_is_sanitized():
    secret = "secret-that-must-not-leak"
    client = GroqClient(api_key=secret)
    client.session = FakeSession(response=FakeResponse(status_code=401, data={"error": secret}))

    with pytest.raises(GroqError) as exc_info:
        client.chat(_ollama_payload())

    assert "HTTP 401" in str(exc_info.value)
    assert secret not in str(exc_info.value)


def test_timeout_is_sanitized():
    secret = "secret-that-must-not-leak"
    client = GroqClient(api_key=secret)
    client.session = FakeSession(error=requests.Timeout(secret))

    with pytest.raises(GroqError) as exc_info:
        client.chat(_ollama_payload())

    assert "tempo de espera" in str(exc_info.value)
    assert secret not in str(exc_info.value)
