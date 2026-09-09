import re
from dataclasses import dataclass
from threading import RLock

LEARNING_RULES_VERSION = 1
MIN_RECURRENCE = 3

OUTCOMES = frozenset(
    {
        "RESOLVED_BY_KNOWLEDGE",
        "GUIDED_BY_PLAYBOOK",
        "ROUTED_TO_HUMAN",
        "APPROVED",
        "REJECTED",
        "DENIED_POLICY",
        "EXECUTION_COMPLETED",
        "EXECUTION_FAILED",
    }
)

_MACHINE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,119}$")


class Phase11LearningError(ValueError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


class OutcomeValidationError(Phase11LearningError):
    pass


class OutcomeConflictError(Phase11LearningError):
    pass


class OutcomeNotFoundError(Phase11LearningError):
    pass


@dataclass(frozen=True)
class OutcomeRecord:
    interaction_id: str
    system: str
    intent: str
    capability: str
    area: str
    knowledge_id: str
    playbook_id: str
    playbook_version: int | None
    step_id: str
    outcome: str
    reason_code: str


def _invalid(message: str) -> None:
    raise OutcomeValidationError("OUTCOME_INVALID", message)


def _required_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        _invalid(f"{field} invalido no OutcomeRecord.")
    return value


def _optional_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit:
        _invalid(f"{field} invalido no OutcomeRecord.")
    return value


def _optional_machine_code(value: object, field: str) -> str:
    text = _optional_text(value, field, 120)
    if text and _MACHINE_CODE_RE.fullmatch(text) is None:
        _invalid(f"{field} deve ser codigo simbolico quando preenchido.")
    return text


def validate_outcome_record(record: OutcomeRecord) -> None:
    if type(record) is not OutcomeRecord:
        _invalid("record deve ser OutcomeRecord imutavel exato.")

    _required_text(record.interaction_id, "interaction_id", 120)
    _required_text(record.system, "system", 120)
    _required_text(record.intent, "intent", 120)
    _optional_machine_code(record.capability, "capability")
    _optional_text(record.area, "area", 180)
    knowledge_id = _optional_text(record.knowledge_id, "knowledge_id", 120)
    playbook_id = _optional_text(record.playbook_id, "playbook_id", 120)
    step_id = _optional_text(record.step_id, "step_id", 120)
    _optional_machine_code(record.reason_code, "reason_code")

    if not isinstance(record.outcome, str) or record.outcome not in OUTCOMES:
        _invalid("outcome fora do vocabulario fechado.")

    if playbook_id:
        if not knowledge_id:
            _invalid("playbook exige knowledge_id.")
        if type(record.playbook_version) is not int or record.playbook_version <= 0:
            _invalid("playbook_version deve ser inteiro positivo com playbook.")
    elif record.playbook_version is not None or step_id:
        _invalid("playbook ausente exige version None e step_id vazio.")


class InMemoryOutcomeStore:
    def __init__(self):
        self._lock = RLock()
        self._records: dict[str, OutcomeRecord] = {}

    def ingest(self, record: OutcomeRecord) -> OutcomeRecord:
        validate_outcome_record(record)
        with self._lock:
            current = self._records.get(record.interaction_id)
            if current is None:
                self._records[record.interaction_id] = record
                return record
            if current == record:
                return current
            raise OutcomeConflictError(
                "OUTCOME_CONFLICT",
                "interaction_id ja possui outcome incompatível.",
            )

    def get(self, interaction_id: str) -> OutcomeRecord:
        with self._lock:
            current = self._records.get(interaction_id)
            if current is None:
                raise OutcomeNotFoundError("OUTCOME_NOT_FOUND", "Outcome inexistente.")
            return current

    def snapshot(self) -> tuple[OutcomeRecord, ...]:
        with self._lock:
            return tuple(self._records[key] for key in sorted(self._records))
