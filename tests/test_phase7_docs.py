from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "policy" / "phase-7.md"
README = ROOT / "README.md"


def test_phase7_operational_doc_locks_policy_boundary() -> None:
    assert DOC.exists()
    text = DOC.read_text(encoding="utf-8")
    for required in (
        "PROBLEMA_ACESSO",
        "CDM_ACCESS_REQUEST",
        "ROLE_CONFLICT",
        "ROLE_PRIVILEGED_INTENT_MATCH",
        "ROLE_PRIVILEGED_NOMINAL_MATCH",
        "ROLE_SOLICITANTE_EXPLICIT",
        "ROLE_PRIVILEGE_AMBIGUOUS",
        "ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE",
        "ROLE_UNRESOLVED",
        "POLICY_NOT_FOUND",
        "POLICY_RULE_INVALID",
        "POLICY_RULE_CONFLICT",
        "CONTEXT_NOT_CDM_ACCESS_REQUEST",
        "AREA_MATCH_REVENDA",
        "PURPOSE_MATCH_MATERIAL_REQUEST",
        "python -m ai_service_desk policy-smoke",
        "319",
        "424",
    ):
        assert required in text


def test_readme_links_phase7_operational_doc() -> None:
    text = README.read_text(encoding="utf-8")
    assert "docs/policy/phase-7.md" in text
