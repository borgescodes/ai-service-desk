"""Loopback-only Ollama client and local embedding adapter."""

from urllib.parse import urlparse

import requests

from ai_service_desk.engine.validation import normalize_matrix


class OllamaError(RuntimeError):
    """Operational error communicating with the local Ollama server."""


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", read_timeout: int = 180):
        url = urlparse(base_url)
        if (
            url.scheme != "http"
            or url.hostname not in ("127.0.0.1", "localhost", "::1")
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
        ):
            raise ValueError("Use somente HTTP em localhost/127.0.0.1/::1 para o Ollama local.")
        if not 1 <= read_timeout <= 1800:
            raise ValueError("Timeout deve estar entre 1 e 1800 segundos.")
        self.base_url = base_url.rstrip("/")
        self.read_timeout = read_timeout
        self.session = requests.Session()
        self.session.trust_env = False
        self._models: dict[str, dict] = {}

    def close(self) -> None:
        self.session.close()

    def _request(self, method: str, path: str, body: dict | None = None) -> requests.Response:
        if not path.startswith("/api/") or "://" in path:
            raise ValueError("Endpoint invalido.")
        try:
            response = self.session.request(
                method,
                self.base_url + path,
                json=body,
                timeout=(5, self.read_timeout),
                allow_redirects=False,
            )
        except requests.Timeout as exc:
            raise OllamaError(
                "Ollama excedeu o tempo de espera. Confira carga da CPU e tente novamente; "
                "o checkpoint foi preservado."
            ) from exc
        except requests.ConnectionError as exc:
            raise OllamaError(
                "Ollama local nao respondeu. Abra o Ollama e confira ollama ps."
            ) from exc
        except requests.RequestException as exc:
            raise OllamaError("Falha de comunicacao com o Ollama local.") from exc
        if 300 <= response.status_code < 400:
            response.close()
            raise OllamaError(
                "Redirecionamento bloqueado. Nenhum dado sera enviado a outro endereco."
            )
        if not 200 <= response.status_code < 300:
            status = response.status_code
            response.close()
            raise OllamaError(
                f"Ollama retornou HTTP {status} em {path}. Confira modelos e tamanho do texto; "
                "nao foi feito download automatico."
            )
        return response

    def json_request(self, method: str, path: str, body: dict | None = None) -> dict:
        response = self._request(method, path, body)
        try:
            data = response.json()
            if not isinstance(data, dict) or data.get("error"):
                raise ValueError
            return data
        except (ValueError, TypeError) as exc:
            raise OllamaError("Resposta JSON invalida do Ollama.") from exc
        finally:
            response.close()

    def version(self) -> str:
        return str(self.json_request("GET", "/api/version").get("version", "nao informado"))

    def model_info(self, name: str) -> dict:
        if not isinstance(name, str) or ":cloud" in name or name.endswith("-cloud"):
            raise ValueError("Modelos cloud nao sao permitidos.")
        if name not in self._models:
            data = self.json_request("GET", "/api/tags")
            models = data.get("models", [])
            if not isinstance(models, list):
                raise OllamaError("Lista de modelos invalida.")
            found = next(
                (
                    model
                    for model in models
                    if isinstance(model, dict) and model.get("name", model.get("model")) == name
                ),
                None,
            )
            if not found:
                raise OllamaError(
                    f"Modelo {name} nao instalado. Confira ollama list. "
                    "O programa nao baixa modelos sozinho."
                )
            if found.get("remote_host") or found.get("remote_model"):
                raise OllamaError("Modelo remoto bloqueado.")
            info = self.json_request("POST", "/api/show", {"model": name})
            if info.get("remote_host") or info.get("remote_model"):
                raise OllamaError("Modelo remoto bloqueado.")
            digest = found.get("digest")
            if not isinstance(digest, str) or not digest:
                raise OllamaError("Modelo sem digest verificavel.")
            self._models[name] = found
        return self._models[name]

    def chat(self, payload: dict) -> dict:
        model = payload.get("model")
        if not isinstance(model, str):
            raise ValueError("Payload de classificacao sem modelo.")
        self.model_info(model)
        return self.json_request("POST", "/api/chat", payload)


class LocalEmbedder:
    def __init__(
        self,
        client: OllamaClient,
        model: str = "qwen3-embedding:0.6b",
        dimensions: int = 1024,
    ):
        self.client = client
        self.model = model
        self.dimensions = dimensions
        self.digest = client.model_info(model)["digest"]

    def embed(self, texts: list[str]):
        if (
            not isinstance(texts, list)
            or not texts
            or any(not isinstance(text, str) or not text.strip() for text in texts)
        ):
            raise ValueError("Embedding requer uma lista de textos nao vazios.")
        data = self.client.json_request(
            "POST",
            "/api/embed",
            {
                "model": self.model,
                "input": texts,
                "truncate": False,
                "keep_alive": "30m",
                "options": {"num_ctx": 4096},
            },
        )
        try:
            matrix = normalize_matrix(data.get("embeddings", []))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Ollama retornou embeddings invalidos.") from exc
        if matrix.shape != (len(texts), self.dimensions):
            raise ValueError(
                f"Esperado embedding ({len(texts)}, {self.dimensions}), recebido {matrix.shape}. "
                "Nao misture indices de modelos diferentes."
            )
        return matrix
