import hashlib
import json
import re

import pytest

from ai_service_desk.engine.ollama import OllamaError
from ai_service_desk.web import demo_runtime
from ai_service_desk.web.errors import WebDemoError


class LocalAIGatewayBase:
    instances = []

    def __init__(self, *args, **kwargs):
        self.payloads = []
        self.embed_requests = []
        self.model_checks = []
        self._models = {}
        self.closed = False
        type(self).instances.append(self)

    def model_info(self, name):
        if name not in self._models:
            self.model_checks.append(name)
            self._models[name] = {"name": name, "digest": f"fake-{name}-digest"}
        return self._models[name]

    @staticmethod
    def _embedding(text: str, dimensions: int = 1024) -> list[float]:
        vector = [0.0] * dimensions
        for token in re.findall(r"[a-z0-9]+", text.casefold()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            vector[index] += 1.0
        if not any(vector):
            vector[0] = 1.0
        return vector

    def json_request(self, method, path, payload=None):
        if method != "POST" or path != "/api/embed" or not isinstance(payload, dict):
            raise AssertionError(f"Unexpected JSON request: {method} {path}")
        texts = payload.get("input")
        if not isinstance(texts, list):
            raise AssertionError("Embedding input must be a list")
        self.embed_requests.append(payload)
        return {"embeddings": [self._embedding(text) for text in texts]}

    def close(self):
        self.closed = True


class ConversationalGateway(LocalAIGatewayBase):
    def chat(self, payload):
        self.payloads.append(payload)
        properties = payload.get("format", {}).get("properties", {})
        text = payload["messages"][-1]["content"].casefold()

        if "relation" in properties:
            if "cdm" in text:
                data = {
                    "relation": "NEW_GOAL",
                    "domain": "IT_SUPPORT",
                    "goal": "REQUEST_ACCESS",
                    "intent": "PROBLEMA_ACESSO",
                    "entities": {"system": "CDM", "product": ""},
                    "facts_added": [],
                    "facts_corrected": [],
                    "answered_pending_question": False,
                    "semantic_signal": "ACCESS_REQUEST",
                    "understood_topic": "acesso ao CDM",
                }
            elif "bolo" in text:
                data = {
                    "relation": "NEW_GOAL",
                    "domain": "OTHER",
                    "goal": "",
                    "intent": "OUTRO",
                    "entities": {"system": "", "product": ""},
                    "facts_added": [],
                    "facts_corrected": [],
                    "answered_pending_question": False,
                    "semantic_signal": "NONE",
                    "understood_topic": "receita culinária",
                }
            elif "bom dia" in text:
                data = {
                    "relation": "NEW_GOAL",
                    "domain": "SOCIAL",
                    "goal": "",
                    "intent": "OUTRO",
                    "entities": {"system": "", "product": ""},
                    "facts_added": [],
                    "facts_corrected": [],
                    "answered_pending_question": False,
                    "semantic_signal": "NONE",
                    "understood_topic": "saudação",
                }
            elif any(term in text for term in ("microsoft 365", "office 365", "office", "outlook")):
                data = {
                    "relation": "NEW_GOAL",
                    "domain": "IT_SUPPORT",
                    "goal": "DIAGNOSE_ISSUE",
                    "intent": "PROBLEMA_ACESSO",
                    "entities": {"system": "OFFICE 365", "product": ""},
                    "facts_added": [],
                    "facts_corrected": [],
                    "answered_pending_question": False,
                    "semantic_signal": (
                        "PASSWORD_EVIDENCE" if "senha" in text else "LOGIN_PROBLEM"
                    ),
                    "understood_topic": "acesso ao Microsoft 365",
                }
            elif "ubs" in text:
                data = {
                    "relation": "NEW_GOAL",
                    "domain": "IT_SUPPORT",
                    "goal": "DIAGNOSE_ISSUE",
                    "intent": "ERRO_SISTEMA",
                    "entities": {"system": "UBS", "product": ""},
                    "facts_added": [],
                    "facts_corrected": [],
                    "answered_pending_question": False,
                    "semantic_signal": "NONE",
                    "understood_topic": "erro no UBS",
                }
            else:
                data = {
                    "relation": "NEW_GOAL",
                    "domain": "IT_SUPPORT",
                    "goal": "DIAGNOSE_ISSUE",
                    "intent": "ERRO_SISTEMA",
                    "entities": {"system": "", "product": ""},
                    "facts_added": [],
                    "facts_corrected": [],
                    "answered_pending_question": False,
                    "semantic_signal": "NONE",
                    "understood_topic": "problema de TI",
                }

            return {
                "message": {
                    "content": json.dumps(
                        data,
                        ensure_ascii=False,
                    )
                },
                "done_reason": "stop",
            }

        if set(properties) == {"intro", "outro"}:
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "intro": "Encontrei uma orientação aprovada.",
                            "outro": "Me diga se resolveu.",
                        },
                        ensure_ascii=False,
                    )
                },
                "done_reason": "stop",
            }

        if set(properties) == {"assistant_message"}:
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "assistant_message": (
                                "Entendi o contexto e vou seguir pelo caminho seguro."
                            )
                        },
                        ensure_ascii=False,
                    )
                },
                "done_reason": "stop",
            }

        raise AssertionError(f"Unexpected conversational schema: {properties}")


class MalformedInterpreterGateway(ConversationalGateway):
    def chat(self, payload):
        properties = payload.get("format", {}).get("properties", {})
        if "relation" in properties:
            self.payloads.append(payload)
            return {
                "message": {"content": "{not-json"},
                "done_reason": "stop",
            }
        return super().chat(payload)


class InvalidInterpreterGateway(ConversationalGateway):
    mode = "extra"

    def chat(self, payload):
        properties = payload.get("format", {}).get("properties", {})
        if "relation" not in properties:
            return super().chat(payload)

        self.payloads.append(payload)

        if self.mode == "malformed":
            content = "{not-json"
            done_reason = "stop"
        else:
            data = {
                "relation": "NEW_GOAL",
                "domain": "IT_SUPPORT",
                "goal": "DIAGNOSE_ISSUE",
                "intent": "ERRO_SISTEMA",
                "entities": {"system": "", "product": ""},
                "facts_added": [],
                "facts_corrected": [],
                "answered_pending_question": False,
                "semantic_signal": "NONE",
                "understood_topic": "problema de TI",
            }

            if self.mode == "extra":
                data["unexpected"] = "field"
                done_reason = "stop"
            elif self.mode == "truncated":
                done_reason = "length"
            else:
                raise AssertionError(self.mode)

            content = json.dumps(data, ensure_ascii=False)

        return {
            "message": {"content": content},
            "done": True,
            "done_reason": done_reason,
        }


class FailingConversationalGateway(LocalAIGatewayBase):
    def chat(self, payload):
        self.payloads.append(payload)
        raise OllamaError("falha local simulada")


def _runtime(monkeypatch, gateway_cls=ConversationalGateway):
    gateway_cls.instances.clear()
    monkeypatch.setattr(demo_runtime, "OllamaClient", gateway_cls)
    return demo_runtime.DemoRuntime.create(mode="LOCAL_AI")


def _first_inference_payload(runtime):
    gateway = runtime._ollama_client
    assert gateway.payloads
    return gateway.payloads[0]


def test_local_ai_turn_uses_interpreter_then_writer(monkeypatch):
    runtime = _runtime(monkeypatch, ConversationalGateway)
    try:
        result = runtime.send_message(
            "pedro-miranda",
            "Preciso acessar o CDM",
        )

        assert result["request_id"]

        payloads = runtime._ollama_client.payloads
        assert len(payloads) == 2
        assert "relation" in payloads[0]["format"]["properties"]
        assert "assistant_message" in payloads[1]["format"]["properties"]
        assert "enum" not in json.dumps(payloads[1]["format"])
    finally:
        runtime.close()


def test_invalid_interpreter_persists_no_turn_or_operation(monkeypatch):
    runtime = _runtime(monkeypatch, MalformedInterpreterGateway)
    try:
        before_requests = list(runtime.created_request_ids)
        before_handoffs = runtime.support_handoff_store.snapshot()
        before_contexts = dict(runtime._conversation_contexts)

        with pytest.raises(WebDemoError) as exc_info:
            runtime.send_message(
                "pedro-miranda",
                "Preciso acessar o CDM",
            )

        assert exc_info.value.code == "LOCAL_AI_RESPONSE_INVALID"
        assert runtime.created_request_ids == before_requests
        assert runtime.support_handoff_store.snapshot() == before_handoffs
        assert runtime._conversation_contexts == before_contexts
    finally:
        runtime.close()


def test_local_ai_social_is_decided_by_interpreter(monkeypatch):
    runtime = _runtime(monkeypatch, ConversationalGateway)
    try:
        before_requests = list(runtime.created_request_ids)
        before_handoffs = runtime.support_handoff_store.snapshot()

        result = runtime.send_message(
            "pedro-miranda",
            "Bom dia",
        )

        assert result["status"] == "SOCIAL"
        assert result["request_id"] is None
        assert result["assistant_message"]

        payloads = runtime._ollama_client.payloads
        assert len(payloads) == 2
        assert "relation" in payloads[0]["format"]["properties"]
        assert "assistant_message" in payloads[1]["format"]["properties"]

        assert runtime.created_request_ids == before_requests
        assert runtime.support_handoff_store.snapshot() == before_handoffs
        assert "pedro-miranda" not in runtime._triage
    finally:
        runtime.close()


def test_local_ai_out_of_scope_is_decided_by_interpreter_without_handoff(monkeypatch):
    runtime = _runtime(monkeypatch, ConversationalGateway)
    try:
        before_requests = list(runtime.created_request_ids)
        before_handoffs = runtime.support_handoff_store.snapshot()

        result = runtime.send_message(
            "pedro-miranda",
            "Como posso fazer bolo?",
        )

        assert result["status"] == "OUT_OF_SCOPE"
        assert result["request_id"] is None
        assert result["support_handoff"] is None
        assert result["understood_topic"] == "receita culinária"
        assert result["business_context"] == {
            "system": "",
            "product": "",
        }
        assert result["assistant_message"]

        payloads = runtime._ollama_client.payloads
        assert len(payloads) == 2
        assert "relation" in payloads[0]["format"]["properties"]
        assert "assistant_message" in payloads[1]["format"]["properties"]

        assert runtime.created_request_ids == before_requests
        assert runtime.support_handoff_store.snapshot() == before_handoffs
        assert "pedro-miranda" not in runtime._triage
    finally:
        runtime.close()


def test_local_ai_unresolved_known_it_routes_to_general_technician(monkeypatch):
    runtime = _runtime(monkeypatch, ConversationalGateway)
    try:
        result = runtime.send_message(
            "pedro-miranda",
            "Estou com erro no UBS",
        )

        assert result["status"] == "SUPPORT_HANDOFF_PENDING"
        assert result["request_id"] is None
        assert result["support_handoff"]["system"] == "UBS"
        assert result["support_handoff"]["technician"]["technician_id"] == "TECH-GENERAL"
        assert result["assistant_message"]

        payloads = runtime._ollama_client.payloads
        assert len(payloads) == 2
        assert "relation" in payloads[0]["format"]["properties"]
        assert "assistant_message" in payloads[1]["format"]["properties"]
    finally:
        runtime.close()


def test_local_ai_uses_contextual_interpreter_then_free_writer_contract(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        runtime.send_message("pedro-miranda", "Nao consigo acessar o sistema.")

        payloads = runtime._ollama_client.payloads
        assert len(payloads) == 2

        payload = payloads[0]
        assert payload["model"] == "qwen3.5:4b"
        assert payload["think"] is False
        assert payload["stream"] is False
        assert payload["keep_alive"] == "30m"
        assert payload["options"] == {
            "temperature": 0,
            "num_ctx": 3072,
            "num_predict": 192,
        }

        schema = payload["format"]
        expected_fields = [
            "relation",
            "domain",
            "goal",
            "intent",
            "entities",
            "facts_added",
            "facts_corrected",
            "answered_pending_question",
            "semantic_signal",
            "understood_topic",
        ]
        assert list(schema["properties"]) == expected_fields
        assert schema["required"] == expected_fields
        assert schema["additionalProperties"] is False
        assert "scenario" not in schema["properties"]
        assert "signal" not in schema["properties"]

        instruction = payload["messages"][0]["content"]
        assert len(instruction) <= 4000
        lowered = instruction.casefold()
        assert "jup" in lowered
        assert "cdm" in lowered
        assert "microsoft 365" in lowered

        writer_schema = payloads[1]["format"]
        assert set(writer_schema["properties"]) == {"assistant_message"}
        assert "enum" not in writer_schema["properties"]["assistant_message"]
    finally:
        runtime.close()


def test_local_ai_never_sends_scenario_signal_or_final_phrase_enum(monkeypatch):
    runtime = _runtime(monkeypatch, ConversationalGateway)
    try:
        runtime.send_message("pedro-miranda", "Bom dia Jup")
        runtime.reset_conversation("pedro-miranda")
        runtime.send_message("pedro-miranda", "Como faço bolo de chocolate?")

        for payload in runtime._ollama_client.payloads:
            schema = json.dumps(payload.get("format", {}), ensure_ascii=False)
            assert '"scenario"' not in schema
            assert '"signal"' not in schema
            assert "Olá, Fulano" not in schema
            assert "Meu foco aqui é suporte de TI" not in schema
    finally:
        runtime.close()


def test_local_ai_metrics_count_calls_turns_and_never_store_content(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        marker = "SEGREDO-NAO-TELEMETRIZAR-84721"
        runtime.send_message("pedro-miranda", f"Nao consigo acessar o sistema. {marker}")
        metrics = runtime.local_ai_metrics()

        assert set(metrics) == {
            "startup_ms",
            "total_calls",
            "failed_calls",
            "calls",
            "turns",
        }
        assert metrics["startup_ms"] >= 0
        assert metrics["total_calls"] == 1
        assert metrics["failed_calls"] == 0
        assert len(metrics["calls"]) == 1
        assert metrics["calls"][0]["duration_ms"] >= 0
        assert metrics["calls"][0]["ok"] is True
        assert metrics["turns"][-1]["call_count"] == 1
        assert metrics["turns"][-1]["duration_ms"] >= 0
        assert marker not in json.dumps(metrics, ensure_ascii=False)
        assert "messages" not in json.dumps(metrics, ensure_ascii=False).casefold()
    finally:
        runtime.close()


def test_local_ai_social_and_out_of_scope_use_interpreter_then_writer(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        gateway = runtime._ollama_client
        gateway.payloads.clear()

        social = runtime.send_message("pedro-miranda", "Bom dia")
        assert social["status"] == "SOCIAL"
        assert len(gateway.payloads) == 2
        assert "relation" in gateway.payloads[0]["format"]["properties"]
        assert "assistant_message" in gateway.payloads[1]["format"]["properties"]
        assert runtime.local_ai_metrics()["turns"][-1]["call_count"] == 1

        gateway.payloads.clear()
        outside = runtime.send_message("pedro-miranda", "Como posso fazer bolo?")
        assert outside["status"] == "OUT_OF_SCOPE"
        assert len(gateway.payloads) == 2
        assert "relation" in gateway.payloads[0]["format"]["properties"]
        assert "assistant_message" in gateway.payloads[1]["format"]["properties"]
        assert runtime.local_ai_metrics()["turns"][-1]["call_count"] == 1
    finally:
        runtime.close()


def test_local_ai_uses_interpreter_and_writer_for_operational_results(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        gateway = runtime._ollama_client
        gateway.payloads.clear()

        created = runtime.send_message("pedro-miranda", "Preciso acessar o CDM.")
        assert created["request_id"]
        assert len(gateway.payloads) == 2
        assert "relation" in gateway.payloads[0]["format"]["properties"]
        assert "assistant_message" in gateway.payloads[1]["format"]["properties"]
        assert runtime.local_ai_metrics()["turns"][-1]["call_count"] == 1

        runtime.reset()
        gateway.payloads.clear()

        guidance = runtime.send_message(
            "pedro-miranda",
            "Esqueci minha senha do Microsoft 365.",
        )
        assert guidance["knowledge_id"] == "KB-SYN-M365-PASSWORD-001"
        assert len(gateway.payloads) == 2
        assert "relation" in gateway.payloads[0]["format"]["properties"]
        assert set(gateway.payloads[1]["format"]["properties"]) == {"intro", "outro"}
        assert runtime.local_ai_metrics()["turns"][-1]["call_count"] == 1
    finally:
        runtime.close()


@pytest.mark.parametrize("mode", ["malformed", "extra", "truncated"])
def test_local_ai_invalid_interpreter_response_fails_closed(monkeypatch, mode):
    InvalidInterpreterGateway.mode = mode
    runtime = _runtime(monkeypatch, InvalidInterpreterGateway)
    try:
        with pytest.raises(WebDemoError) as exc_info:
            runtime.send_message("pedro-miranda", "Nao consigo acessar o sistema.")
        assert exc_info.value.code == "LOCAL_AI_RESPONSE_INVALID"
        assert runtime.local_ai_metrics()["failed_calls"] == 1
    finally:
        runtime.close()


def test_local_ai_transport_failure_is_explicit_and_counted(monkeypatch):
    runtime = _runtime(monkeypatch, FailingConversationalGateway)
    try:
        with pytest.raises(WebDemoError) as exc_info:
            runtime.send_message("pedro-miranda", "Nao consigo acessar o sistema.")
        assert exc_info.value.code == "LOCAL_AI_INFERENCE_FAILED"
        metrics = runtime.local_ai_metrics()
        assert metrics["total_calls"] == 1
        assert metrics["failed_calls"] == 1
    finally:
        runtime.close()


def test_local_ai_startup_validates_models_without_warmup_chat(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        gateway = runtime._ollama_client
        assert gateway.model_checks == ["qwen3.5:4b", "qwen3-embedding:0.6b"]
        assert gateway.embed_requests
        assert all(request["model"] == "qwen3-embedding:0.6b" for request in gateway.embed_requests)
        assert gateway.payloads == []
        metrics = runtime.local_ai_metrics()
        assert metrics["startup_ms"] >= 0
        assert metrics["total_calls"] == 0
        assert metrics["calls"] == []
        assert metrics["turns"] == []
    finally:
        runtime.close()
