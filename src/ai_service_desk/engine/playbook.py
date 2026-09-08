import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from ai_service_desk.engine.index import atomic_json
from ai_service_desk.engine.knowledge import load_knowledge_index

PLAYBOOK_SCHEMA_VERSION = 1
PLAYBOOK_CATALOG_SCHEMA_VERSION = 1
PLAYBOOK_DOMAIN = "APPROVED_PLAYBOOK"
CATALOG_RECIPE = "playbook-catalog-v1"
PLAYBOOK_CATALOG_FILE = "playbook-catalog.json"
PLAYBOOK_PROVENANCE_FILE = "playbook-provenance.json"
ALLOWED_PLAYBOOK_STATUSES = {"DRAFT", "APPROVED", "RETIRED"}
ALLOWED_STEP_TYPES = {"INSTRUCTION", "CHECK", "ACTION_PROPOSAL"}
CAPABILITY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,119}$")
PLAYBOOK_FIELDS = {
    "playbook_id",
    "title",
    "description",
    "knowledge_ids",
    "steps",
    "source",
    "status",
    "reviewed_by",
    "reviewed_at",
    "version",
}
STEP_FIELDS = {"step_id", "type", "title", "instruction", "capability"}


def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _required_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} deve ser texto nao vazio com ate {limit} caracteres.")
    return value


def _optional_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"{field} deve ser texto com ate {limit} caracteres.")
    return value


def _validate_reviewed_at(value: str) -> None:
    if not value:
        return
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("reviewed_at deve ser ISO 8601 com timezone.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("reviewed_at deve ser ISO 8601 com timezone.")


def _validate_step(raw: object) -> dict:
    if not isinstance(raw, dict) or set(raw) != STEP_FIELDS:
        raise ValueError("campos de step invalidos.")
    step = dict(raw)
    _required_text(step["step_id"], "step_id", 120)
    _required_text(step["title"], "title", 180)
    _required_text(step["instruction"], "instruction", 1500)
    capability = _optional_text(step["capability"], "capability", 120)
    step_type = step["type"]
    if not isinstance(step_type, str) or step_type not in ALLOWED_STEP_TYPES:
        raise ValueError("type de step invalido.")
    if step_type == "ACTION_PROPOSAL":
        if not CAPABILITY_RE.fullmatch(capability):
            raise ValueError("ACTION_PROPOSAL exige capability simbolica valida.")
    elif capability:
        raise ValueError("capability deve ser vazia para INSTRUCTION e CHECK.")
    return step


def _validate_playbook(raw: object) -> dict:
    if not isinstance(raw, dict) or set(raw) != PLAYBOOK_FIELDS:
        raise ValueError("campos de playbook invalidos.")
    playbook = dict(raw)
    _required_text(playbook["playbook_id"], "playbook_id", 120)
    _required_text(playbook["title"], "title", 180)
    _required_text(playbook["description"], "description", 1000)
    _required_text(playbook["source"], "source", 120)
    reviewed_by = _optional_text(playbook["reviewed_by"], "reviewed_by", 120)
    reviewed_at = _optional_text(playbook["reviewed_at"], "reviewed_at", 80)

    status = playbook["status"]
    if not isinstance(status, str) or status not in ALLOWED_PLAYBOOK_STATUSES:
        raise ValueError("status deve ser DRAFT, APPROVED ou RETIRED.")
    _validate_reviewed_at(reviewed_at)
    if status == "APPROVED" and (not reviewed_by.strip() or not reviewed_at):
        raise ValueError("Playbook APPROVED exige reviewed_by e reviewed_at validos.")

    version = playbook["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise ValueError("version deve ser inteiro positivo.")

    knowledge_ids = playbook["knowledge_ids"]
    if not isinstance(knowledge_ids, list) or not 1 <= len(knowledge_ids) <= 20:
        raise ValueError("knowledge_ids deve conter de 1 a 20 itens.")
    seen_knowledge: set[str] = set()
    for knowledge_id in knowledge_ids:
        value = _required_text(knowledge_id, "knowledge_id", 120)
        if value in seen_knowledge:
            raise ValueError(f"knowledge_id duplicado no playbook: {value}")
        seen_knowledge.add(value)

    steps = playbook["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
        raise ValueError("steps deve conter de 1 a 20 itens.")
    validated_steps: list[dict] = []
    seen_steps: set[str] = set()
    for raw_step in steps:
        step = _validate_step(raw_step)
        step_id = step["step_id"]
        if step_id in seen_steps:
            raise ValueError(f"step_id duplicado: {step_id}")
        seen_steps.add(step_id)
        validated_steps.append(step)
    playbook["steps"] = validated_steps
    playbook["knowledge_ids"] = list(knowledge_ids)
    return playbook


def load_playbooks(path: str | Path) -> list[dict]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ValueError("Arquivo de playbooks nao encontrado.")
    rows: list[dict] = []
    seen: set[str] = set()
    try:
        with source.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"JSON invalido na linha {line_number}.") from exc
                playbook = _validate_playbook(raw)
                playbook_id = playbook["playbook_id"]
                if playbook_id in seen:
                    raise ValueError(f"playbook_id duplicado: {playbook_id}")
                seen.add(playbook_id)
                rows.append(playbook)
    except UnicodeDecodeError as exc:
        raise ValueError("Playbooks devem ser JSONL UTF-8 valido.") from exc
    if not rows:
        raise ValueError("Base de playbooks vazia.")
    return rows


def _compile_catalog_rows(playbooks: list[dict], eligible_ids: set[str]) -> dict:
    approved_playbooks: dict[str, dict] = {}
    active_by_knowledge_id: dict[str, str] = {}
    inactive_by_knowledge_id: dict[str, list[dict]] = {}
    for playbook in playbooks:
        playbook_id = playbook["playbook_id"]
        for knowledge_id in playbook["knowledge_ids"]:
            if knowledge_id not in eligible_ids:
                raise ValueError(f"referencia de knowledge nao elegivel: {knowledge_id}")
        if playbook["status"] == "APPROVED":
            operational = {
                "playbook_id": playbook_id,
                "title": playbook["title"],
                "description": playbook["description"],
                "knowledge_ids": list(playbook["knowledge_ids"]),
                "version": playbook["version"],
                "steps": [dict(step) for step in playbook["steps"]],
            }
            approved_playbooks[playbook_id] = operational
            for knowledge_id in playbook["knowledge_ids"]:
                if knowledge_id in active_by_knowledge_id:
                    raise ValueError(
                        f"knowledge_id possui mais de um playbook APPROVED: {knowledge_id}"
                    )
                active_by_knowledge_id[knowledge_id] = playbook_id
        else:
            metadata = {
                "playbook_id": playbook_id,
                "status": playbook["status"],
                "version": playbook["version"],
            }
            for knowledge_id in playbook["knowledge_ids"]:
                inactive_by_knowledge_id.setdefault(knowledge_id, []).append(dict(metadata))
    return {
        "playbooks": approved_playbooks,
        "active_by_knowledge_id": active_by_knowledge_id,
        "inactive_by_knowledge_id": inactive_by_knowledge_id,
    }


def build_playbook_catalog(
    source: str | Path,
    knowledge_index_directory: str | Path,
    output_directory: str | Path,
) -> dict:
    data, _, knowledge_provenance = load_knowledge_index(knowledge_index_directory)
    if "knowledge_id" not in data.columns:
        raise ValueError("Indice APPROVED_KNOWLEDGE sem knowledge_id.")
    eligible_ids = set(data["knowledge_id"].astype(str).tolist())
    if not eligible_ids:
        raise ValueError("Indice APPROVED_KNOWLEDGE sem knowledge elegivel.")
    playbooks = load_playbooks(source)
    compiled = _compile_catalog_rows(playbooks, eligible_ids)
    return {
        **compiled,
        "approved_playbooks": len(compiled["playbooks"]),
        "active_links": len(compiled["active_by_knowledge_id"]),
        "inactive_links": sum(len(rows) for rows in compiled["inactive_by_knowledge_id"].values()),
        "knowledge_provenance": knowledge_provenance,
        "eligible_knowledge_ids": sorted(eligible_ids),
    }
