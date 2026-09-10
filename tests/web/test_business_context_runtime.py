import json

import pytest

from ai_service_desk.web import demo_runtime


class SemanticGateway:
    def __init__(self):
        self.payloads = []

    def model_info(self, name):
        return {"name": name}

    def close(self):
        pass

    def chat(self, payload):
        self.payloads.append(payload)
        if "intent" not in payload["format"]["properties"]:
            options = payload["format"]["properties"]["assistant_message"].get("enum")
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "assistant_message": options[0] if options else "Entendi seu relato.",
                        }
                    )
                }
            }
        text = payload["messages"][-1]["content"].casefold()
        return {
            "message": {
                "content": json.dumps(
                    {
                        "intent": "ORIENTACAO" if "cadastrar" in text else "PROBLEMA_ACESSO",
                        "system": "",
                        "entities": {"product": "INVENTADO"},
                        "confidence": 0.95,
                    }
                )
            }
        }


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setattr(demo_runtime, "OllamaClient", SemanticGateway)
    instance = demo_runtime.DemoRuntime.create(mode="LOCAL_AI")
    yield instance
    instance.close()


@pytest.mark.parametrize(
    "text,system,product",
    [
        ("Esqueci minha senha do Office", "OFFICE 365", ""),
        ("Meu Teams não entra", "OFFICE 365", "TEAMS"),
        ("Teams no Office 365 não entra", "OFFICE 365", "TEAMS"),
        ("Outlook não abre", "OFFICE 365", "OUTLOOK"),
        ("O One Drive não sincroniza", "OFFICE 365", "ONEDRIVE"),
        ("Portal RH não abre", "PORTAL RH", ""),
        ("Metadados não entra", "METADADOS", ""),
        ("O SAP está com erro", "SAP", ""),
        ("Ordem de compra no CIGAM", "CIGAM 11", ""),
        ("O SIAGRI está travando", "SIAGRI", ""),
    ],
)
def test_runtime_consumes_single_vocabulary_without_redundant_clarification(
    runtime,
    text,
    system,
    product,
):
    result = runtime.send_message("pedro-miranda", text)
    state = runtime._triage["pedro-miranda"][1]
    assert state.system == system
    assert state.entities.get("product", "") == product
    assert result["status"] != "NEEDS_CLARIFICATION"
    assert result["request_id"] is None
    assert runtime.conversations["pedro-miranda"][-1]["text"] == text
    assert state.problem_text == text
    assert result["business_context"]["system"] == system
    assert result["business_context"]["product"] == product


def test_runtime_contextual_cdm_does_not_fabricate_access_or_knowledge(runtime):
    result = runtime.send_message("pedro-miranda", "Preciso cadastrar material para revenda")
    assert runtime._triage["pedro-miranda"][1].system == "CDM"
    assert result["status"] == "TRIAGE_ABSTAINED"
    assert result["request_id"] is None
    assert runtime.created_request_ids == []


def test_runtime_real_ambiguity_and_follow_up_use_original_context(runtime):
    first = runtime.send_message("pedro-miranda", "Não consigo acessar o sistema")
    assert first["status"] == "NEEDS_CLARIFICATION"
    second = runtime.send_message("pedro-miranda", "Central de Dados Mestres")
    state = runtime._triage["pedro-miranda"][1]
    assert state.system == "CDM"
    assert state.problem_text == "Não consigo acessar o sistema"
    assert second["reason"] if "reason" in second else second["request_id"]
    assert second["status"] != "NEEDS_CLARIFICATION"


def test_prompt_context_does_not_replace_user_text_or_expand_approved_systems(runtime):
    message = "Bom dia Jup, preciso comprar material"
    runtime.send_message("pedro-miranda", message)
    payload = runtime._ollama_client.payloads[0]
    assert payload["messages"][-1]["content"] == message
    assert "BUSINESS_CONTEXT_CURRENT" in payload["messages"][0]["content"]
    assert runtime.knowledge_engine.available_systems("PROBLEMA_ACESSO") == ("CDM", "OFFICE 365")
    assert runtime._triage["pedro-miranda"][1].system == ""
