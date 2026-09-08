from collections.abc import Mapping
from pathlib import Path

from ai_service_desk.engine.playbook import load_playbook_catalog


class PlaybookEngine:
    def __init__(
        self,
        catalog_directory: str | Path,
        knowledge_index_directory: str | Path,
    ):
        self.catalog, self.provenance = load_playbook_catalog(
            catalog_directory,
            knowledge_index_directory,
        )
        self._eligible = set(self.catalog["eligible_knowledge_ids"])

    def resolve(self, knowledge: Mapping[str, object]) -> dict:
        if not isinstance(knowledge, Mapping):
            raise ValueError("knowledge deve ser mapping com knowledge_id.")
        return self.resolve_knowledge_id(knowledge.get("knowledge_id"))

    def resolve_knowledge_id(self, knowledge_id: str) -> dict:
        if not isinstance(knowledge_id, str) or not knowledge_id.strip() or len(knowledge_id) > 120:
            raise ValueError("knowledge_id invalido.")
        if knowledge_id not in self._eligible:
            raise ValueError("knowledge_id nao e elegivel no catalogo aprovado.")

        active_id = self.catalog["active_by_knowledge_id"].get(knowledge_id)
        if active_id is not None:
            source = self.catalog["playbooks"][active_id]
            return {
                "status": "PLAYBOOK_FOUND",
                "reason": "MATCH",
                "knowledge_id": knowledge_id,
                "playbook": {
                    "playbook_id": source["playbook_id"],
                    "title": source["title"],
                    "description": source["description"],
                    "playbook_version": source["version"],
                    "steps": [dict(step) for step in source["steps"]],
                },
            }

        inactive = self.catalog["inactive_by_knowledge_id"].get(knowledge_id, [])
        statuses = {row["status"] for row in inactive}
        if "DRAFT" in statuses:
            return {
                "status": "PLAYBOOK_UNAVAILABLE",
                "reason": "PLAYBOOK_NOT_APPROVED",
                "knowledge_id": knowledge_id,
                "playbook": None,
            }
        if "RETIRED" in statuses:
            return {
                "status": "PLAYBOOK_UNAVAILABLE",
                "reason": "PLAYBOOK_RETIRED",
                "knowledge_id": knowledge_id,
                "playbook": None,
            }
        return {
            "status": "KNOWLEDGE_ONLY",
            "reason": "NO_PLAYBOOK",
            "knowledge_id": knowledge_id,
            "playbook": None,
        }


def action_proposal_descriptor(
    knowledge_id: str,
    playbook: Mapping[str, object],
    step: Mapping[str, object],
) -> dict:
    if not isinstance(step, Mapping) or step.get("type") != "ACTION_PROPOSAL":
        raise ValueError("step nao e ACTION_PROPOSAL")
    capability = step.get("capability")
    if not isinstance(capability, str) or not capability:
        raise ValueError("ACTION_PROPOSAL sem capability valida")
    return {
        "knowledge_id": knowledge_id,
        "playbook_id": playbook["playbook_id"],
        "playbook_version": playbook["playbook_version"],
        "step_id": step["step_id"],
        "type": "ACTION_PROPOSAL",
        "capability": capability,
    }


def format_playbook_result(result: Mapping[str, object]) -> str:
    status = result.get("status")
    if status == "KNOWLEDGE_ONLY":
        return ""
    if status == "PLAYBOOK_UNAVAILABLE":
        return (
            "Ha um procedimento relacionado, mas ele nao esta disponivel "
            "para orientacao neste momento."
        )
    if status != "PLAYBOOK_FOUND":
        raise ValueError("resultado de playbook invalido para formatacao.")

    playbook = result.get("playbook")
    if not isinstance(playbook, Mapping):
        raise ValueError("resultado PLAYBOOK_FOUND sem playbook valido.")
    lines = [str(playbook["title"]), str(playbook["description"])]
    steps = playbook.get("steps")
    if not isinstance(steps, list):
        raise ValueError("playbook sem steps validos.")
    for raw_step in steps:
        if not isinstance(raw_step, Mapping):
            raise ValueError("step invalido para formatacao.")
        if raw_step.get("type") == "ACTION_PROPOSAL":
            lines.append("Acao proposta:")
        lines.append(str(raw_step["title"]))
        lines.append(str(raw_step["instruction"]))
    return "\n".join(lines)
