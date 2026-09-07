import json
from pathlib import Path

import pytest

from ai_service_desk.engine.corpus import audit_corpus, ensure_external_path

FIXTURE = Path("tests/fixtures/phase2_corpus.csv")
MANIFEST = Path("tests/fixtures/phase2_corpus_manifest.json")


def test_audit_returns_only_aggregate_contract() -> None:
    report = audit_corpus(FIXTURE)

    assert report["rows"] == 3
    assert report["unique_ticket_ids"] == 3
    assert report["empty_ticket_ids"] == 0
    assert report["empty_search_texts"] == 0
    assert report["with_history"] == 2
    assert report["limited_texts"] == 1
    assert report["knowledge_status"] == {"HISTORICO_NAO_VALIDADO": 3}
    assert report["privacy"]["anonymization_claim"] is False
    serialized = str(report)
    assert "Falha CIGAM" not in serialized
    assert "1001" not in serialized
    assert "Atendimento sintetico" not in serialized


def test_audit_detects_risk_counts_without_values(tmp_path: Path) -> None:
    source = FIXTURE.read_text(encoding="utf-8-sig")
    risky = tmp_path / "risky.csv"
    risky.write_text(
        source.replace("Erro sintetico", "email pessoa@example.com"),
        encoding="utf-8-sig",
    )

    report = audit_corpus(risky)

    assert report["risk_counts"]["email"] > 0
    assert "pessoa@example.com" not in str(report)


def test_external_path_rejects_checkout_children(tmp_path: Path) -> None:
    checkout = tmp_path / "repo"
    checkout.mkdir()

    with pytest.raises(ValueError, match="fora do checkout"):
        ensure_external_path(checkout / "data" / "corpus.csv", checkout)

    external = tmp_path / "external" / "corpus.csv"
    assert ensure_external_path(external, checkout) == external.resolve()


def test_audit_accepts_matching_manifest() -> None:
    report = audit_corpus(FIXTURE, MANIFEST)

    assert report["manifest_match"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rows", 4),
        ("with_history", 3),
        ("limited_texts", 0),
        ("raw_sha256", "0" * 64),
        ("canonical_sha256", "f" * 64),
    ],
)
def test_audit_rejects_manifest_expected_mismatch(
    tmp_path: Path, field: str, value: object
) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["expected"][field] = value
    changed = tmp_path / "manifest.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Snapshot divergente"):
        audit_corpus(FIXTURE, changed)


def test_audit_rejects_manifest_schema_mismatch(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["columns"] = manifest["columns"][:-1]
    changed = tmp_path / "manifest.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Schema"):
        audit_corpus(FIXTURE, changed)


def test_audit_rejects_invalid_knowledge_status_even_with_matching_hashes(tmp_path: Path) -> None:
    source = FIXTURE.read_text(encoding="utf-8-sig")
    invalid = tmp_path / "invalid-status.csv"
    invalid.write_text(
        source.replace("HISTORICO_NAO_VALIDADO", "VALIDADO"),
        encoding="utf-8-sig",
    )
    baseline = audit_corpus(invalid)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["expected"]["raw_sha256"] = baseline["raw_sha256"]
    manifest["expected"]["canonical_sha256"] = baseline["canonical_sha256"]
    changed = tmp_path / "manifest.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="status_conhecimento"):
        audit_corpus(invalid, changed)
