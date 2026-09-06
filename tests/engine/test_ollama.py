import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

from ai_service_desk.engine.classification import classify_ticket
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient, OllamaError


class Handler(BaseHTTPRequestHandler):
    requests_seen: list[tuple[str, dict]] = []

    def log_message(self, *args: object) -> None:
        return None

    def answer(self, obj: dict, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self) -> None:
        if self.path == "/api/tags":
            self.answer(
                {
                    "models": [
                        {"name": "qwen3-embedding:0.6b", "digest": "test-digest"},
                        {"name": "qwen3.5:4b", "digest": "chat-test-digest"},
                        {
                            "name": "remote:1b",
                            "digest": "remote-digest",
                            "remote_host": "https://example.com",
                        },
                    ]
                }
            )
        elif self.path == "/api/version":
            self.answer({"version": "test-version"})
        else:
            self.answer({"error": "missing"}, 404)

    def do_POST(self) -> None:
        size = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(size).decode("utf-8")) if size else {}
        Handler.requests_seen.append((self.path, body))
        if self.path == "/api/chat":
            self.answer(
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "intent": "LIBERACAO_ROTINA",
                                "system": "",
                                "entities": {"rotina": "1024"},
                                "confidence": 0.9,
                            }
                        )
                    },
                    "done": True,
                }
            )
        elif self.path == "/api/embed":
            if body["input"] == ["invalid"]:
                self.answer({"embeddings": [[0, 0, 0]]})
            else:
                self.answer({"embeddings": [[3, 4, 0] for _ in body["input"]]})
        elif self.path == "/api/show":
            self.answer({"capabilities": ["embedding"]})
        elif self.path == "/api/redirect":
            self.send_response(302)
            self.send_header("Location", "http://example.com")
            self.end_headers()
        elif self.path == "/api/broken":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"bad-json")
        else:
            self.answer({"error": "test"}, 500)


@pytest.fixture
def server_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_remote_and_malformed_base_urls_are_refused() -> None:
    for url in (
        "https://ollama.com",
        "http://example.com:11434",
        "http://user:pass@127.0.0.1:11434",
        "http://127.0.0.1:11434/path",
        "http://127.0.0.1:11434/?x=1",
    ):
        with pytest.raises(ValueError):
            OllamaClient(url)


def test_proxy_environment_is_disabled(server_url: str) -> None:
    client = OllamaClient(server_url)
    try:
        assert client.session.trust_env is False
    finally:
        client.close()


def test_models_version_and_missing_model(server_url: str) -> None:
    client = OllamaClient(server_url)
    try:
        assert client.version() == "test-version"
        assert client.model_info("qwen3-embedding:0.6b")["digest"] == "test-digest"
        with pytest.raises(OllamaError, match="nao instalado"):
            client.model_info("missing:1b")
        with pytest.raises(OllamaError, match="remoto"):
            client.model_info("remote:1b")
    finally:
        client.close()


def test_classifier_runs_through_real_http_boundary(server_url: str) -> None:
    client = OllamaClient(server_url)
    try:
        result = classify_ticket("libera a rotina 1024 no CIGAM", client.chat)
        assert result.system == "CIGAM"
        assert result.entities["rotina"] == "1024"
        assert Handler.requests_seen[-1][1]["think"] is False
    finally:
        client.close()


def test_batch_embedding_is_normalized_and_disables_truncation(server_url: str) -> None:
    client = OllamaClient(server_url)
    try:
        embedder = LocalEmbedder(client, dimensions=3)
        matrix = embedder.embed(["impressora nao imprime", "CIGAM"])
        assert matrix.shape == (2, 3)
        np.testing.assert_allclose(matrix[0], [0.6, 0.8, 0.0])
        assert Handler.requests_seen[-1][1]["truncate"] is False
    finally:
        client.close()


def test_invalid_embedding_redirect_malformed_json_and_cloud_are_refused(server_url: str) -> None:
    client = OllamaClient(server_url)
    try:
        with pytest.raises(ValueError):
            LocalEmbedder(client, dimensions=3).embed(["invalid"])
        with pytest.raises(OllamaError, match="Redirecionamento"):
            client.json_request("POST", "/api/redirect", {})
        with pytest.raises(OllamaError, match="JSON"):
            client.json_request("POST", "/api/broken", {})
        with pytest.raises(ValueError, match="cloud"):
            client.model_info("qwen3:cloud")
    finally:
        client.close()


def test_endpoint_outside_api_is_refused(server_url: str) -> None:
    client = OllamaClient(server_url)
    try:
        with pytest.raises(ValueError):
            client.json_request("GET", "/other")
    finally:
        client.close()
