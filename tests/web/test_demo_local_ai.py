import json

import pytest

from ai_service_desk.engine.ollama import OllamaError
from ai_service_desk.web import demo_runtime
from ai_service_desk.web.business_context import BusinessVocabulary
from ai_service_desk.web.demo_ai import compact_interpretation_to_classification
from ai_service_desk.web.errors import WebDemoError


class CompactGateway:
    instances = []

    def __init__(self, *args, **kwargs):
        self.payloads = []
        self.model_checks = []
        self.closed = False
        type(self).instances.append(self)

    def model_info(self, name):
        self.model_checks.append(name)
        return {"name": name, "digest": "fake-qwen-digest"}

    def chat(self, payload):
        self.payloads.append(payload)
        properties = payload.get("format", {}).get("properties", {})
        text = payload["messages"][-1]["content"].casefold()
        if "scenario" in properties:
            if (
                "cdm" in text
                or "central de dados mestres" in text
                or ("material" in text and "revenda" in text)
            ):
                signal = (
                    "PRIVILEGED_ACCESS"
                    if any(term in text for term in ("admin", "administrador", "superadmin"))
                    else "ACCESS_REQUEST"
                )
                result = {"scenario": "CDM_ACCESS", "signal": signal}
            elif "365" in text or "office" in text or "outlook" in text:
                result = {"scenario": "M365_SUPPORT", "signal": "PASSWORD_EVIDENCE"}
            else:
                result = {"scenario": "OTHER_IT", "signal": "UNKNOWN"}
        else:
            # Compatibilidade apenas para provar o RED contra o contrato antigo.
            result = {
                "intent": "PROBLEMA_ACESSO",
                "system": "CDM" if "cdm" in text else "",
                "entities": {},
                "confidence": 0.95,
            }
        return {
            "message": {"content": json.dumps(result)},
            "done": True,
            "done_reason": "stop",
        }

    def close(self):
        self.closed = True


class InvalidCompactGateway(CompactGateway):
    mode = "extra"

    def chat(self, payload):
        self.payloads.append(payload)
        properties = payload.get("format", {}).get("properties", {})
        if "scenario" not in properties:
            return super().chat(payload)
        if self.mode == "malformed":
            content = "{not-json"
            done_reason = "stop"
        elif self.mode == "extra":
            content = json.dumps({"scenario": "OTHER_IT", "signal": "UNKNOWN", "confidence": 0.9})
            done_reason = "stop"
        elif self.mode == "truncated":
            content = json.dumps({"scenario": "OTHER_IT", "signal": "UNKNOWN"})
            done_reason = "length"
        else:
            raise AssertionError(self.mode)
        return {
            "message": {"content": content},
            "done": True,
            "done_reason": done_reason,
        }


class FailingCompactGateway(CompactGateway):
    def chat(self, payload):
        self.payloads.append(payload)
        raise OllamaError("falha local simulada")


def _runtime(monkeypatch, gateway_cls=CompactGateway):
    gateway_cls.instances.clear()
    monkeypatch.setattr(demo_runtime, "OllamaClient", gateway_cls)
    return demo_runtime.DemoRuntime.create(mode="LOCAL_AI")


def _first_inference_payload(runtime):
    gateway = runtime._ollama_client
    assert gateway.payloads
    return gateway.payloads[0]


def test_local_ai_uses_compact_scenario_signal_contract_and_small_payload(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        runtime.send_message("pedro-miranda", "Nao consigo acessar o sistema.")
        payload = _first_inference_payload(runtime)

        assert payload["model"] == "qwen3.5:4b"
        assert payload["think"] is False
        assert payload["stream"] is False
        assert payload["keep_alive"] == "30m"
        assert payload["options"]["temperature"] == 0
        assert 32 <= payload["options"]["num_predict"] <= 48
        assert payload["options"]["num_ctx"] <= 1024

        schema = payload["format"]
        assert set(schema["properties"]) == {"scenario", "signal"}
        assert schema["required"] == ["scenario", "signal"]
        assert schema["additionalProperties"] is False
        assert schema["properties"]["scenario"]["enum"] == [
            "CDM_ACCESS",
            "M365_SUPPORT",
            "OTHER_IT",
            "UNKNOWN",
        ]
        assert schema["properties"]["signal"]["enum"] == [
            "ACCESS_REQUEST",
            "PRIVILEGED_ACCESS",
            "LOGIN_PROBLEM",
            "PASSWORD_EVIDENCE",
            "SUCCESS",
            "FAILURE",
            "UNKNOWN",
        ]

        instruction = payload["messages"][0]["content"]
        assert len(instruction) <= 700
        lowered = instruction.casefold()
        assert "jup" in lowered
        assert "ti" in lowered
        assert "cdm" in lowered
        assert "microsoft 365" in lowered
        for broad_system in ("siagri", "cigam", "portal rh", "metadados"):
            assert broad_system not in lowered
    finally:
        runtime.close()


@pytest.mark.parametrize(
    "text,scenario,signal,expected_intent,expected_system",
    [
        (
            "Preciso cadastrar um material para revenda",
            "CDM_ACCESS",
            "ACCESS_REQUEST",
            "ORIENTACAO",
            "CDM",
        ),
        (
            "Bom dia! Preciso cadastrar material para revenda no SIAGRI",
            "CDM_ACCESS",
            "ACCESS_REQUEST",
            "ORIENTACAO",
            "SIAGRI",
        ),
        (
            "Preciso de acesso ao CDM",
            "CDM_ACCESS",
            "ACCESS_REQUEST",
            "PROBLEMA_ACESSO",
            "CDM",
        ),
        (
            "Nao consigo entrar no CDM",
            "CDM_ACCESS",
            "LOGIN_PROBLEM",
            "PROBLEMA_ACESSO",
            "CDM",
        ),
        (
            "Preciso de acesso administrador ao CDM",
            "CDM_ACCESS",
            "PRIVILEGED_ACCESS",
            "PROBLEMA_ACESSO",
            "CDM",
        ),
        (
            "Preciso instalar o Teams",
            "OTHER_IT",
            "UNKNOWN",
            "INSTALACAO_SOFTWARE",
            "OFFICE 365",
        ),
    ],
)
def test_compact_interpretation_requires_textual_access_evidence(
    text,
    scenario,
    signal,
    expected_intent,
    expected_system,
):
    classification = compact_interpretation_to_classification(
        text,
        scenario,
        signal,
        BusinessVocabulary(),
    )

    assert classification.intent == expected_intent
    assert classification.system == expected_system


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


def test_local_ai_zero_call_turns_are_measured_without_inference(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        gateway = runtime._ollama_client
        gateway.payloads.clear()

        runtime.send_message("pedro-miranda", "Bom dia")
        assert len(gateway.payloads) == 0
        assert runtime.local_ai_metrics()["turns"][-1]["call_count"] == 0

        runtime.send_message("pedro-miranda", "Quanto foi o jogo do Flamengo?")
        assert len(gateway.payloads) == 0
        assert runtime.local_ai_metrics()["turns"][-1]["call_count"] == 0
    finally:
        runtime.close()


def test_local_ai_never_uses_second_inference_to_render_backend_results(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        gateway = runtime._ollama_client
        gateway.payloads.clear()

        created = runtime.send_message("pedro-miranda", "Preciso acessar o CDM.")
        assert created["request_id"]
        assert len(gateway.payloads) == 1
        assert runtime.local_ai_metrics()["turns"][-1]["call_count"] == 1

        runtime.reset()
        gateway.payloads.clear()
        guidance = runtime.send_message("pedro-miranda", "Esqueci minha senha do Microsoft 365.")
        assert guidance["knowledge_id"] == "KB-SYN-M365-PASSWORD-001"
        assert len(gateway.payloads) <= 1

        gateway.payloads.clear()
        resolved = runtime.send_message("pedro-miranda", "Funcionou.")
        assert resolved["resolved"] is True
        assert gateway.payloads == []
        assert runtime.local_ai_metrics()["turns"][-1]["call_count"] == 0
    finally:
        runtime.close()


@pytest.mark.parametrize("mode", ["malformed", "extra", "truncated"])
def test_local_ai_invalid_compact_response_fails_closed(monkeypatch, mode):
    InvalidCompactGateway.mode = mode
    runtime = _runtime(monkeypatch, InvalidCompactGateway)
    try:
        with pytest.raises(WebDemoError) as exc_info:
            runtime.send_message("pedro-miranda", "Nao consigo acessar o sistema.")
        assert exc_info.value.code == "LOCAL_AI_RESPONSE_INVALID"
        assert runtime.local_ai_metrics()["failed_calls"] == 1
    finally:
        runtime.close()


def test_local_ai_transport_failure_is_explicit_and_counted(monkeypatch):
    runtime = _runtime(monkeypatch, FailingCompactGateway)
    try:
        with pytest.raises(WebDemoError) as exc_info:
            runtime.send_message("pedro-miranda", "Nao consigo acessar o sistema.")
        assert exc_info.value.code == "LOCAL_AI_INFERENCE_FAILED"
        metrics = runtime.local_ai_metrics()
        assert metrics["total_calls"] == 1
        assert metrics["failed_calls"] == 1
    finally:
        runtime.close()


def test_local_ai_startup_validates_model_without_warmup_call(monkeypatch):
    runtime = _runtime(monkeypatch)
    try:
        gateway = runtime._ollama_client
        assert gateway.model_checks == ["qwen3.5:4b"]
        assert gateway.payloads == []
        metrics = runtime.local_ai_metrics()
        assert metrics["startup_ms"] >= 0
        assert metrics["total_calls"] == 0
        assert metrics["calls"] == []
        assert metrics["turns"] == []
    finally:
        runtime.close()
