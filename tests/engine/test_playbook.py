import inspect
import json
from pathlib import Path

import pandas as pd
import pytest

from ai_service_desk.engine.playbook import build_playbook_catalog, load_playbooks


def valid_step(step_id='STEP-01', step_type='INSTRUCTION', capability=''):
    return {
        'step_id': step_id,
        'type': step_type,
        'title': 'Passo sintetico',
        'instruction': 'Execute apenas a verificacao ficticia descrita.',
        'capability': capability,
    }


def valid_playbook(playbook_id='PB-SYN-001', status='APPROVED', knowledge_ids=None, steps=None):
    return {
        'playbook_id': playbook_id,
        'title': 'Playbook sintetico',
        'description': 'Procedimento totalmente sintetico para testes.',
        'knowledge_ids': knowledge_ids if knowledge_ids is not None else ['KB-SYN-PRINT-001'],
        'steps': steps if steps is not None else [valid_step()],
        'source': 'SYNTHETIC_DEMO',
        'status': status,
        'reviewed_by': 'synthetic-reviewer' if status == 'APPROVED' else '',
        'reviewed_at': '2026-09-08T01:00:00-03:00' if status == 'APPROVED' else '',
        'version': 1,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


def assert_rejected(tmp_path: Path, row: dict, match: str = '') -> None:
    source = tmp_path / 'bad.jsonl'
    write_jsonl(source, [row])
    with pytest.raises(ValueError, match=match or None):
        load_playbooks(source)


def test_load_playbooks_accepts_strict_valid_source(tmp_path: Path) -> None:
    source = tmp_path / 'playbooks.jsonl'
    write_jsonl(source, [valid_playbook()])
    rows = load_playbooks(source)
    assert len(rows) == 1
    assert rows[0]['playbook_id'] == 'PB-SYN-001'


def test_load_playbooks_rejects_missing_field(tmp_path: Path) -> None:
    row = valid_playbook(); row.pop('description')
    assert_rejected(tmp_path, row, 'campos de playbook invalidos')


def test_load_playbooks_rejects_extra_field(tmp_path: Path) -> None:
    row = valid_playbook(); row['unexpected'] = True
    assert_rejected(tmp_path, row, 'campos de playbook invalidos')


def test_rejects_duplicate_playbook_id(tmp_path: Path) -> None:
    source = tmp_path / 'dup.jsonl'; write_jsonl(source, [valid_playbook(), valid_playbook()])
    with pytest.raises(ValueError, match='duplicado'): load_playbooks(source)


def test_rejects_empty_source(tmp_path: Path) -> None:
    source = tmp_path / 'empty.jsonl'; source.write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='vazia'): load_playbooks(source)


def test_rejects_invalid_utf8(tmp_path: Path) -> None:
    source = tmp_path / 'bad.jsonl'; source.write_bytes(b'\xff\xfe')
    with pytest.raises(ValueError, match='UTF-8'): load_playbooks(source)


def test_rejects_invalid_json(tmp_path: Path) -> None:
    source = tmp_path / 'bad.jsonl'; source.write_text('{not-json}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='JSON'): load_playbooks(source)


def test_rejects_invalid_status(tmp_path: Path) -> None:
    row = valid_playbook(); row['status'] = 'ACTIVE'; assert_rejected(tmp_path, row, 'status')


def test_rejects_approved_without_reviewer(tmp_path: Path) -> None:
    row = valid_playbook(); row['reviewed_by'] = ''; assert_rejected(tmp_path, row, 'APPROVED')


def test_rejects_approved_without_reviewed_at(tmp_path: Path) -> None:
    row = valid_playbook(); row['reviewed_at'] = ''; assert_rejected(tmp_path, row, 'APPROVED')


def test_rejects_reviewed_at_without_timezone(tmp_path: Path) -> None:
    row = valid_playbook(); row['reviewed_at'] = '2026-09-08T01:00:00'; assert_rejected(tmp_path, row, 'timezone')


def test_rejects_boolean_version(tmp_path: Path) -> None:
    row = valid_playbook(); row['version'] = True; assert_rejected(tmp_path, row, 'inteiro positivo')


def test_rejects_zero_version(tmp_path: Path) -> None:
    row = valid_playbook(); row['version'] = 0; assert_rejected(tmp_path, row, 'inteiro positivo')


def test_rejects_duplicate_knowledge_id_inside_playbook(tmp_path: Path) -> None:
    row = valid_playbook(knowledge_ids=['KB-SYN-PRINT-001', 'KB-SYN-PRINT-001']); assert_rejected(tmp_path, row, 'knowledge_id duplicado')


def test_rejects_empty_knowledge_ids(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(knowledge_ids=[]), 'knowledge_ids')


def test_rejects_more_than_20_knowledge_ids(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(knowledge_ids=[f'KB-SYN-{i:03d}' for i in range(21)]), 'knowledge_ids')


def test_rejects_empty_steps(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(steps=[]), 'steps')


def test_rejects_more_than_20_steps(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(steps=[valid_step(f'STEP-{i:02d}') for i in range(21)]), 'steps')


def test_rejects_duplicate_step_id(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(steps=[valid_step(), valid_step()]), 'step_id duplicado')


def test_rejects_invalid_step_type(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(steps=[valid_step(step_type='EXECUTE')]), 'type')


def test_action_proposal_requires_capability(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(steps=[valid_step(step_type='ACTION_PROPOSAL')]), 'capability')


def test_instruction_rejects_capability(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(steps=[valid_step(capability='DEMO_X')]), 'capability')


def test_check_rejects_capability(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(steps=[valid_step(step_type='CHECK', capability='DEMO_X')]), 'capability')


def test_rejects_invalid_capability(tmp_path: Path) -> None:
    assert_rejected(tmp_path, valid_playbook(steps=[valid_step(step_type='ACTION_PROPOSAL', capability='pwsh.exe')]), 'capability')

@pytest.mark.parametrize(('field','size'), [('playbook_id',121), ('title',181), ('description',1001)])
def test_rejects_overlong_playbook_fields(tmp_path: Path, field: str, size: int) -> None:
    row = valid_playbook(); row[field] = 'x' * size; assert_rejected(tmp_path, row, field)


def test_rejects_overlong_step_instruction(tmp_path: Path) -> None:
    step = valid_step(); step['instruction'] = 'x' * 1501; assert_rejected(tmp_path, valid_playbook(steps=[step]), 'instruction')

@pytest.mark.parametrize('status', ['DRAFT', 'APPROVED', 'RETIRED'])
def test_accepts_official_lifecycle(tmp_path: Path, status: str) -> None:
    source = tmp_path / f'{status}.jsonl'; write_jsonl(source, [valid_playbook(status=status)])
    assert load_playbooks(source)[0]['status'] == status

@pytest.mark.parametrize(('step_type','capability'), [('INSTRUCTION',''), ('CHECK',''), ('ACTION_PROPOSAL','DEMO_PRINT_QUEUE_CLEAR')])
def test_accepts_official_step_types(tmp_path: Path, step_type: str, capability: str) -> None:
    source = tmp_path / 'good.jsonl'; write_jsonl(source, [valid_playbook(steps=[valid_step(step_type=step_type, capability=capability)])])
    assert load_playbooks(source)[0]['steps'][0]['type'] == step_type


def trusted_knowledge_provenance(rows: int, source_hash: str = "b" * 64) -> dict:
    return {
        "version": 1,
        "domain": "APPROVED_KNOWLEDGE",
        "knowledge_schema_version": 1,
        "projection_recipe": "knowledge-search-v1",
        "approved_only": True,
        "source_hash": source_hash,
        "matrix_hash": "c" * 64,
        "rows": rows,
        "dimensions": 1024,
        "model": "qwen3-embedding:0.6b",
        "model_digest": "d" * 64,
        "index_recipe": "texto_busca-plain-v1",
    }


def trusted_index_double(ids: list[str], source_hash: str = "b" * 64):
    data = pd.DataFrame({"knowledge_id": ids})
    return data, object(), trusted_knowledge_provenance(len(ids), source_hash)


def test_build_uses_validated_knowledge_index_loader(monkeypatch, tmp_path: Path) -> None:
    calls: list[Path] = []
    def fake_load(path):
        calls.append(Path(path))
        return trusted_index_double(["KB-SYN-PRINT-001"])
    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", fake_load)
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
    assert calls == [tmp_path / "knowledge"]


def test_build_public_signature_has_no_raw_provenance() -> None:
    assert list(inspect.signature(build_playbook_catalog).parameters) == [
        "source", "knowledge_index_directory", "output_directory"
    ]


def test_build_accepts_reference_present_in_approved_index(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", lambda path: trusted_index_double(["KB-SYN-PRINT-001"]))
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    result = build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
    assert result["active_links"] == 1


def test_build_rejects_reference_absent_from_approved_index(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", lambda path: trusted_index_double(["KB-SYN-OTHER-001"]))
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    with pytest.raises(ValueError, match="referencia de knowledge nao elegivel"):
        build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")


def test_one_approved_playbook_can_link_multiple_knowledge_ids(monkeypatch, tmp_path: Path) -> None:
    ids = ["KB-SYN-CIGAM-ACCESS-001", "KB-SYN-SIAGRI-ACCESS-001"]
    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", lambda path: trusted_index_double(ids))
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook(knowledge_ids=ids)])
    result = build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
    assert result["active_links"] == 2


def test_two_approved_playbooks_for_same_knowledge_reject_build(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", lambda path: trusted_index_double(["KB-SYN-PRINT-001"]))
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook("PB-SYN-A"), valid_playbook("PB-SYN-B")])
    with pytest.raises(ValueError, match="mais de um playbook APPROVED"):
        build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")


def test_inactive_playbooks_share_knowledge_without_active_conflict(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", lambda path: trusted_index_double(["KB-SYN-PRINT-001"]))
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook("PB-SYN-D", status="DRAFT"), valid_playbook("PB-SYN-R", status="RETIRED")])
    out = tmp_path / "catalog"
    result = build_playbook_catalog(source, tmp_path / "knowledge", out)
    assert result["active_links"] == 0
    assert result["inactive_links"] == 2
    catalog = json.loads((out / "playbook-catalog.json").read_text(encoding="utf-8"))
    assert catalog["inactive_by_knowledge_id"]["KB-SYN-PRINT-001"] == [
        {"playbook_id": "PB-SYN-D", "status": "DRAFT", "version": 1},
        {"playbook_id": "PB-SYN-R", "status": "RETIRED", "version": 1},
    ]


def test_build_is_deterministic(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-PRINT-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    first = build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "first")
    second = build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "second")
    assert first == second
    assert first["catalog_hash"] == second["catalog_hash"]
    first_catalog = json.loads(
        (tmp_path / "first" / "playbook-catalog.json").read_text(encoding="utf-8")
    )
    second_catalog = json.loads(
        (tmp_path / "second" / "playbook-catalog.json").read_text(encoding="utf-8")
    )
    assert first_catalog == second_catalog


def test_provenance_binds_source_catalog_and_knowledge(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import canonical_json_bytes, sha256_bytes

    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-PRINT-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    out = tmp_path / "catalog"
    provenance = build_playbook_catalog(source, tmp_path / "knowledge", out)
    catalog = json.loads((out / "playbook-catalog.json").read_text(encoding="utf-8"))
    assert set(provenance) == {
        "version",
        "domain",
        "playbook_schema_version",
        "catalog_schema_version",
        "catalog_recipe",
        "source_hash",
        "catalog_hash",
        "approved_playbooks",
        "active_links",
        "inactive_links",
        "knowledge_domain",
        "knowledge_schema_version",
        "knowledge_source_hash",
        "knowledge_provenance_hash",
    }
    assert provenance["domain"] == "APPROVED_PLAYBOOK"
    assert provenance["source_hash"] == catalog["source_hash"]
    assert provenance["knowledge_domain"] == catalog["knowledge_binding"]["domain"]
    assert provenance["knowledge_schema_version"] == catalog["knowledge_binding"]["schema_version"]
    assert provenance["knowledge_source_hash"] == catalog["knowledge_binding"]["source_hash"]
    assert provenance["knowledge_provenance_hash"] == catalog["knowledge_binding"]["provenance_hash"]
    assert provenance["catalog_hash"] == sha256_bytes(canonical_json_bytes(catalog))
    assert provenance["approved_playbooks"] == 1
    assert provenance["active_links"] == 1
    assert provenance["inactive_links"] == 0


def test_provenance_sidecar_is_last_write(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-PRINT-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])

    from ai_service_desk.engine import playbook as module

    writes: list[str] = []
    real_atomic = module.atomic_json

    def recording_atomic(path, payload):
        writes.append(Path(path).name)
        return real_atomic(path, payload)

    monkeypatch.setattr(module, "atomic_json", recording_atomic)
    build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
    assert writes == ["playbook-catalog.json", "playbook-provenance.json"]


def test_load_rejects_missing_sidecar(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-PRINT-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    out = tmp_path / "catalog"
    write_jsonl(source, [valid_playbook()])
    build_playbook_catalog(source, tmp_path / "knowledge", out)
    (out / "playbook-provenance.json").unlink()
    with pytest.raises(ValueError, match="provenance"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def _build_valid_catalog(monkeypatch, tmp_path: Path, rows=None, ids=None, name="catalog"):
    trusted_ids = ids or ["KB-SYN-PRINT-001"]
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(trusted_ids),
    )
    source = tmp_path / f"{name}.jsonl"
    write_jsonl(source, rows or [valid_playbook()])
    out = tmp_path / name
    build_playbook_catalog(source, tmp_path / "knowledge", out)
    return source, out


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _rewrite_catalog_and_refresh_hash(out: Path, mutate) -> None:
    from ai_service_desk.engine.playbook import canonical_json_bytes, sha256_bytes

    catalog_path = out / "playbook-catalog.json"
    sidecar_path = out / "playbook-provenance.json"
    catalog = _read_json(catalog_path)
    mutate(catalog)
    _write_json(catalog_path, catalog)
    sidecar = _read_json(sidecar_path)
    sidecar["catalog_hash"] = sha256_bytes(canonical_json_bytes(catalog))
    _write_json(sidecar_path, sidecar)


def test_load_rejects_sidecar_from_other_catalog(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, first = _build_valid_catalog(monkeypatch, tmp_path, name="first")
    changed = valid_playbook("PB-SYN-OTHER")
    changed["title"] = "Outro playbook sintetico"
    _, second = _build_valid_catalog(monkeypatch, tmp_path, rows=[changed], name="second")
    (first / "playbook-provenance.json").write_bytes(
        (second / "playbook-provenance.json").read_bytes()
    )
    with pytest.raises(ValueError):
        load_playbook_catalog(first, tmp_path / "knowledge")


def test_load_rejects_catalog_hash_mismatch(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    catalog = _read_json(out / "playbook-catalog.json")
    catalog["playbooks"]["PB-SYN-001"]["title"] = "Adulterado"
    _write_json(out / "playbook-catalog.json", catalog)
    with pytest.raises(ValueError, match="hash|diverg"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_truncated_catalog(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    path = out / "playbook-catalog.json"
    raw = path.read_bytes()
    path.write_bytes(raw[: len(raw) // 2])
    with pytest.raises(ValueError):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_partial_catalog_schema(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    _rewrite_catalog_and_refresh_hash(out, lambda c: c.pop("active_by_knowledge_id"))
    with pytest.raises(ValueError, match="catalogo"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_wrong_catalog_domain(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    _rewrite_catalog_and_refresh_hash(out, lambda c: c.__setitem__("domain", "HISTORICO_NAO_VALIDADO"))
    with pytest.raises(ValueError, match="dominio"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_wrong_sidecar_domain(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    sidecar_path = out / "playbook-provenance.json"
    sidecar = _read_json(sidecar_path)
    sidecar["domain"] = "OTHER_DOMAIN"
    _write_json(sidecar_path, sidecar)
    with pytest.raises(ValueError, match="provenance"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_extra_provenance_field(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    sidecar_path = out / "playbook-provenance.json"
    sidecar = _read_json(sidecar_path)
    sidecar["unexpected"] = True
    _write_json(sidecar_path, sidecar)
    with pytest.raises(ValueError, match="provenance"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_wrong_knowledge_source_hash(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    sidecar_path = out / "playbook-provenance.json"
    sidecar = _read_json(sidecar_path)
    sidecar["knowledge_source_hash"] = "e" * 64
    _write_json(sidecar_path, sidecar)
    with pytest.raises(ValueError, match="knowledge"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_wrong_knowledge_provenance_hash(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    sidecar_path = out / "playbook-provenance.json"
    sidecar = _read_json(sidecar_path)
    sidecar["knowledge_provenance_hash"] = "e" * 64
    _write_json(sidecar_path, sidecar)
    with pytest.raises(ValueError, match="knowledge"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_catalog_sidecar_binding_mismatch(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    def mutate(c):
        c["knowledge_binding"]["source_hash"] = "e" * 64
    _rewrite_catalog_and_refresh_hash(out, mutate)
    with pytest.raises(ValueError, match="knowledge|binding"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_active_link_to_missing_playbook(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    def mutate(c):
        c["active_by_knowledge_id"]["KB-SYN-PRINT-001"] = "PB-SYN-MISSING"
    _rewrite_catalog_and_refresh_hash(out, mutate)
    with pytest.raises(ValueError, match="active|playbook|propriet"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_active_link_outside_eligible_ids(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    def mutate(c):
        c["active_by_knowledge_id"]["KB-SYN-NOT-ELIGIBLE-001"] = "PB-SYN-001"
    _rewrite_catalog_and_refresh_hash(out, mutate)
    with pytest.raises(ValueError, match="elegivel|active|propriet"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_inactive_instruction(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    rows = [valid_playbook("PB-SYN-D", status="DRAFT")]
    _, out = _build_valid_catalog(monkeypatch, tmp_path, rows=rows)
    def mutate(c):
        c["inactive_by_knowledge_id"]["KB-SYN-PRINT-001"][0]["instruction"] = "Nao pode aparecer"
    _rewrite_catalog_and_refresh_hash(out, mutate)
    with pytest.raises(ValueError, match="inativ|metadata"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_inactive_capability(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    rows = [valid_playbook("PB-SYN-D", status="DRAFT")]
    _, out = _build_valid_catalog(monkeypatch, tmp_path, rows=rows)
    def mutate(c):
        c["inactive_by_knowledge_id"]["KB-SYN-PRINT-001"][0]["capability"] = "DEMO_X"
    _rewrite_catalog_and_refresh_hash(out, mutate)
    with pytest.raises(ValueError, match="inativ|metadata"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_rejects_two_approved_owners_even_if_active_map_has_one(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    _, out = _build_valid_catalog(monkeypatch, tmp_path)
    def mutate(c):
        second = dict(c["playbooks"]["PB-SYN-001"])
        second["playbook_id"] = "PB-SYN-SECOND"
        c["playbooks"]["PB-SYN-SECOND"] = second
    _rewrite_catalog_and_refresh_hash(out, mutate)
    sidecar_path = out / "playbook-provenance.json"
    sidecar = _read_json(sidecar_path)
    sidecar["approved_playbooks"] = 2
    _write_json(sidecar_path, sidecar)
    with pytest.raises(ValueError, match="mais de um|propriet"):
        load_playbook_catalog(out, tmp_path / "knowledge")


def test_load_revalidates_current_knowledge_index(monkeypatch, tmp_path: Path) -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    calls: list[Path] = []
    trusted = trusted_index_double(["KB-SYN-PRINT-001"])
    def fake_loader(path):
        calls.append(Path(path))
        return trusted
    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", fake_loader)
    source = tmp_path / "playbooks.jsonl"
    out = tmp_path / "catalog"
    write_jsonl(source, [valid_playbook()])
    build_playbook_catalog(source, tmp_path / "knowledge", out)
    calls.clear()
    load_playbook_catalog(out, tmp_path / "knowledge")
    assert calls == [tmp_path / "knowledge"]


def test_load_public_signature_has_only_validated_knowledge_index() -> None:
    from ai_service_desk.engine.playbook import load_playbook_catalog

    assert list(inspect.signature(load_playbook_catalog).parameters) == [
        "directory",
        "knowledge_index_directory",
    ]
