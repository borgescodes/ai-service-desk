import json
from pathlib import Path

import pytest

from ai_service_desk.engine.playbook import load_playbooks


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
