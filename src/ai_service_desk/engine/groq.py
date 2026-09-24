"""Minimal Groq adapter for the existing Ollama-shaped chat contract."""

import os

import requests

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


class GroqError(RuntimeError):
    """Operational error communicating with Groq."""


class GroqClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        read_timeout: int = 180,
    ) -> None:
        resolved_api_key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY")
        if not isinstance(resolved_api_key, str) or not resolved_api_key.strip():
            raise ValueError("GROQ_API_KEY deve estar definida para usar o provider Groq.")
        resolved_model = (
            model if model is not None else os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        )
        if not isinstance(resolved_model, str) or not resolved_model.strip():
            raise ValueError("GROQ_MODEL deve informar um modelo válido.")
        if not 1 <= read_timeout <= 1800:
            raise ValueError("Timeout deve estar entre 1 e 1800 segundos.")

        self._api_key = resolved_api_key.strip()
        self.model = resolved_model.strip()
        self.read_timeout = read_timeout
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    def chat(self, payload: dict) -> dict:
        options = payload.get("options", {})
        request_payload = {
            "model": self.model,
            "messages": payload["messages"],
            "stream": False,
            "temperature": options["temperature"],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "jup_response",
                    "strict": False,
                    "schema": payload["format"],
                },
            },
        }
        if "num_predict" in options:
            request_payload["max_completion_tokens"] = max(options["num_predict"], 1024)
        try:
            response = self.session.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=(5, self.read_timeout),
                allow_redirects=False,
            )
        except requests.Timeout as exc:
            raise GroqError("Groq excedeu o tempo de espera.") from exc
        except requests.RequestException as exc:
            raise GroqError("Falha de comunicação com a Groq.") from exc

        try:
            if not 200 <= response.status_code < 300:
                raise GroqError(f"Groq retornou HTTP {response.status_code}.")
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish_reason = choice["finish_reason"]
            if not isinstance(content, str) or not isinstance(finish_reason, str):
                raise TypeError
            return {
                "message": {"content": content},
                "done_reason": finish_reason,
            }
        except GroqError:
            raise
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise GroqError("Resposta JSON inválida da Groq.") from exc
        finally:
            response.close()
