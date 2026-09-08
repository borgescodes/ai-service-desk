import math

import pytest

from ai_service_desk.engine.classification import (
    ALLOWED_INTENTS,
    build_payload,
    classify_ticket,
    explicit_systems,
    validate_classification,
)


def response(content: str, **extra: object) -> dict:
    return {"message": {"content": content}, **extra}


def test_payload_disables_thinking_and_closes_schema() -> None:
    payload = build_payload("o cigam fecha quando tento faturar")
    assert payload["model"] == "qwen3.5:4b"
    assert payload["think"] is False
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["num_ctx"] == 4096
    assert payload["options"]["num_predict"] == 384
    assert payload["format"]["additionalProperties"] is False
    assert set(payload["format"]["properties"]["intent"]["enum"]) == ALLOWED_INTENTS


def test_build_payload_rejects_invalid_input_before_transport() -> None:
    for value in ("", "   ", None):
        with pytest.raises(ValueError):
            build_payload(value)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        build_payload("x" * 3001)


def test_validate_classification_accepts_unknown_literal_system() -> None:
    result = validate_classification(
        {"intent": "ERRO_SISTEMA", "system": "XYZ", "entities": {}, "confidence": 0.74}
    )
    assert result.system == "XYZ"


@pytest.mark.parametrize(
    "bad",
    [
        {"intent": "INVENTADO", "system": "", "entities": {}, "confidence": 0.5},
        {"intent": "OUTRO", "system": None, "entities": {}, "confidence": 0.5},
        {"intent": "OUTRO", "system": "", "entities": {"x": 1}, "confidence": 0.5},
        {"intent": "OUTRO", "system": "", "entities": {}, "confidence": True},
        {"intent": "OUTRO", "system": "", "entities": {}, "confidence": math.nan},
        {"intent": "OUTRO", "system": "", "entities": {}, "confidence": math.inf},
        {"intent": "OUTRO", "system": "", "entities": {}, "confidence": 1.1},
        {"intent": "OUTRO", "system": "", "entities": {}, "confidence": -0.1},
        {"intent": "OUTRO", "system": "", "entities": {}, "confidence": 0.5, "extra": 1},
    ],
)
def test_validate_classification_rejects_contract_violations(bad: dict) -> None:
    with pytest.raises(ValueError):
        validate_classification(bad)


def test_explicit_cigam_overrides_invented_model_system_and_routine() -> None:
    result = classify_ticket(
        "preciso liberar a rotina 001024 no CIGAM",
        lambda payload: response(
            '{"intent":"LIBERACAO_ROTINA","system":"SAP","entities":{"rotina":"123"},"confidence":0.85}'
        ),
    )
    assert result.system == "CIGAM"
    assert result.entities["rotina"] == "001024"


def test_explicit_unknown_system_is_preserved_from_literal_text() -> None:
    result = classify_ticket(
        "o sistema XYZ trava quando salvo",
        lambda payload: response(
            '{"intent":"ERRO_SISTEMA","system":"","entities":{},"confidence":0.8}'
        ),
    )
    assert result.system == "XYZ"


def test_invented_system_is_removed_when_not_literal() -> None:
    result = classify_ticket(
        "aplicativo trava ao salvar",
        lambda payload: response(
            '{"intent":"ERRO_SISTEMA","system":"SAP","entities":{},"confidence":0.7}'
        ),
    )
    assert result.system == ""


def test_multiple_explicit_systems_are_ambiguous() -> None:
    assert explicit_systems("integracao entre CIGAM e SIAGRI falhou") == ["CIGAM", "SIAGRI"]
    result = classify_ticket(
        "integracao entre CIGAM e SIAGRI falhou",
        lambda payload: response(
            '{"intent":"ERRO_SISTEMA","system":"CIGAM","entities":{},"confidence":0.8}'
        ),
    )
    assert result.system == ""


def test_literal_branch_is_preserved_and_model_entity_is_removed() -> None:
    result = classify_ticket(
        "erro na filial 003 do CIGAM",
        lambda payload: response(
            '{"intent":"ERRO_SISTEMA","system":"CIGAM","entities":{"branch":"999","equipamento":"PC-1"},"confidence":0.8}'
        ),
    )
    assert result.entities == {"equipamento": "PC-1", "filial": "003"}


def test_supercigam_does_not_match_cigam_alias() -> None:
    assert explicit_systems("supercigam travou") == []


def test_generic_words_do_not_become_systems() -> None:
    result = classify_ticket(
        "o sistema travou",
        lambda payload: response(
            '{"intent":"ERRO_SISTEMA","system":"sistema","entities":{},"confidence":0.8}'
        ),
    )
    assert result.system == ""


def test_done_reason_length_aborts_classification() -> None:
    with pytest.raises(ValueError, match="limite"):
        classify_ticket(
            "cigam com erro",
            lambda payload: response(
                '{"intent":"ERRO_SISTEMA","system":"CIGAM","entities":{},"confidence":0.8}',
                done_reason="length",
            ),
        )


def test_invalid_json_aborts_classification() -> None:
    with pytest.raises(ValueError, match="JSON"):
        classify_ticket("cigam com erro", lambda payload: response("not json"))


def test_siagri_literal_is_preserved() -> None:
    result = classify_ticket(
        "o SIAGRI esta fora",
        lambda payload: response(
            '{"intent":"ERRO_SISTEMA","system":"","entities":{},"confidence":0.8}'
        ),
    )
    assert result.system == "SIAGRI"


def test_routine_is_not_fabricated_without_literal_evidence() -> None:
    result = classify_ticket(
        "o cigam nao abre",
        lambda payload: response(
            '{"intent":"ERRO_SISTEMA","system":"CIGAM","entities":{"rotina":"1024"},"confidence":0.8}'
        ),
    )
    assert "rotina" not in result.entities


def test_equipment_name_is_not_promoted_to_software_system() -> None:
    result = classify_ticket(
        "impressora nao imprime",
        lambda payload: response(
            '{"intent":"PROBLEMA_IMPRESSAO","system":"impressora","entities":{},"confidence":0.8}'
        ),
    )
    assert result.system == ""


def test_explicit_systems_recognizes_cdm() -> None:
    assert explicit_systems("acesso ao CDM") == ["CDM"]


def test_cdm_and_cigam_are_multi_system_context() -> None:
    text = "acesso ao CDM e CIGAM"
    assert set(explicit_systems(text)) == {"CDM", "CIGAM"}
    result = classify_ticket(
        text,
        lambda payload: response(
            '{"intent":"PROBLEMA_ACESSO","system":"CDM","entities":{},"confidence":0.9}'
        ),
    )
    assert result.system == ""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("erro no CIGAM", ["CIGAM"]),
        ("erro no SIAGRI", ["SIAGRI"]),
        ("erro no Outlook", ["OUTLOOK"]),
        ("erro no Teams", ["TEAMS"]),
        ("erro no Microsoft 365", ["OFFICE 365"]),
        ("erro no WhatsApp", ["WHATSAPP"]),
        ("erro no Windows", ["WINDOWS"]),
    ],
)
def test_existing_system_aliases_remain_recognized(text: str, expected: list[str]) -> None:
    assert explicit_systems(text) == expected
