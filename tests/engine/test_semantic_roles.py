import pytest

from ai_service_desk.engine.access_request import normalize_requested_role


@pytest.mark.parametrize(
    ("text", "expected_role"),
    [
        ("preciso de acesso adm no cdm", "ADMIN"),
        ("preciso de acesso administrativo ao cdm", "ADMIN"),
        ("preciso de acesso administrador ao cdm", "ADMIN"),
        ("preciso de acesso administradora ao cdm", "ADMIN"),
        ("quero superadmin no cdm", "SUPERADMIN"),
    ],
)
def test_privileged_role_aliases_are_normalized_before_policy(text: str, expected_role: str) -> None:
    role, reason = normalize_requested_role(text)

    assert role == expected_role
    assert reason == "ROLE_PRIVILEGED_NOMINAL_MATCH"
