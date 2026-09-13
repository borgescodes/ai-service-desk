import json

import numpy as np

from ai_service_desk.engine.classification import classify_ticket
from ai_service_desk.web.demo_ai import DemoClassifierClient, DemoEmbedder


def test_cdm_access_text_uses_core_classifier_contract() -> None:
    result = classify_ticket(
        "Preciso de acesso ao CDM para solicitar materiais para uma revenda.",
        DemoClassifierClient().chat,
    )
    assert result.intent == "PROBLEMA_ACESSO"
    assert result.system == "CDM"
    assert result.confidence == 0.92


def test_m365_password_text_maps_to_office_365() -> None:
    result = classify_ticket(
        "Não consigo acessar o Microsoft 365 depois que esqueci minha senha.",
        DemoClassifierClient().chat,
    )
    assert result.intent == "PROBLEMA_ACESSO"
    assert result.system == "OFFICE 365"


def test_unknown_text_abstains_from_system() -> None:
    result = classify_ticket("Preciso de ajuda com uma coisa.", DemoClassifierClient().chat)
    assert result.intent == "OUTRO"
    assert result.system == ""


def test_classifier_reads_only_core_user_message_not_identity_fields() -> None:
    payload = {
        "messages": [
            {"role": "system", "content": "contract"},
            {"role": "user", "content": "Preciso de acesso ao CDM."},
        ],
        "identity": "tecnico-cdm",
        "username": "forged.user",
    }
    content = json.loads(DemoClassifierClient().chat(payload)["message"]["content"])
    assert content["system"] == "CDM"
    assert set(content) == {"intent", "system", "entities", "confidence"}


def test_demo_embedder_is_fixed_deterministic_float32_matrix() -> None:
    embedder = DemoEmbedder()
    first = embedder.embed(["acesso cdm", "office 365 senha"])
    second = embedder.embed(["acesso cdm", "office 365 senha"])

    assert embedder.model == "jup-demo-hash-v1"
    assert embedder.digest == "phase12-demo-embedder-v1"
    assert embedder.dimensions == 32
    assert first.shape == (2, 32)
    assert first.dtype == np.float32
    np.testing.assert_array_equal(first, second)
