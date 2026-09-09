import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock

from ai_service_desk.engine.request_lifecycle import (
    AccessRequestRecord,
    validate_access_request_record,
)
from ai_service_desk.engine.routing import RoutingAssignment
from ai_service_desk.engine.triage import TriageState

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

OPPORTUNITY_CATEGORIES = (
    "KNOWLEDGE_GAP",
    "PLAYBOOK_GAP",
    "HUMAN_DEPENDENCY",
    "AUTOMATION_CANDIDATE",
    "PREVENTION_CANDIDATE",
    "EXECUTION_RELIABILITY_ISSUE",
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


@dataclass(frozen=True, order=True)
class PatternKey:
    system: str
    intent: str
    capability: str
    area: str


@dataclass(frozen=True)
class PatternAggregate:
    key: PatternKey
    occurrence_count: int
    evidence_ids: tuple[str, ...]
    outcome_counts: tuple[tuple[str, int], ...]
    knowledge_count: int
    knowledge_ids: tuple[str, ...]
    playbook_count: int
    playbook_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class PreventionOpportunity:
    opportunity_id: str
    category: str
    key: PatternKey
    occurrence_count: int
    evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


def _invalid(message: str) -> None:
    raise OutcomeValidationError("OUTCOME_INVALID", message)


def _evidence_invalid(message: str) -> None:
    raise OutcomeValidationError("OUTCOME_EVIDENCE_INVALID", message)


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


class OutcomeCollector:
    @staticmethod
    def from_knowledge(
        interaction_id: str,
        triage: TriageState,
        result: Mapping[str, object],
        *,
        area: str = "",
    ) -> OutcomeRecord:
        if type(triage) is not TriageState or triage.status != "ANSWERED":
            _evidence_invalid("Knowledge exige triage ANSWERED.")
        if not isinstance(result, Mapping) or result.get("status") != "KNOWLEDGE_FOUND":
            _evidence_invalid("Resultado de Knowledge nao comprova resolucao.")
        knowledge = result.get("knowledge")
        if not isinstance(knowledge, Mapping):
            _evidence_invalid("KNOWLEDGE_FOUND sem knowledge estruturado.")
        knowledge_id = knowledge.get("knowledge_id")
        if not isinstance(knowledge_id, str) or not knowledge_id.strip():
            _evidence_invalid("KNOWLEDGE_FOUND sem knowledge_id.")
        record = OutcomeRecord(
            interaction_id=interaction_id,
            system=triage.system,
            intent=triage.intent,
            capability="",
            area=area,
            knowledge_id=knowledge_id,
            playbook_id="",
            playbook_version=None,
            step_id="",
            outcome="RESOLVED_BY_KNOWLEDGE",
            reason_code="KNOWLEDGE_FOUND",
        )
        validate_outcome_record(record)
        return record

    @staticmethod
    def from_playbook(
        interaction_id: str,
        triage: TriageState,
        result: Mapping[str, object],
        *,
        area: str = "",
    ) -> OutcomeRecord:
        if type(triage) is not TriageState or triage.status != "ANSWERED":
            _evidence_invalid("Playbook exige triage ANSWERED.")
        if not isinstance(result, Mapping) or result.get("status") != "PLAYBOOK_FOUND":
            _evidence_invalid("Resultado nao comprova PLAYBOOK_FOUND.")
        knowledge_id = result.get("knowledge_id")
        playbook = result.get("playbook")
        if not isinstance(knowledge_id, str) or not knowledge_id.strip():
            _evidence_invalid("PLAYBOOK_FOUND sem knowledge_id.")
        if not isinstance(playbook, Mapping):
            _evidence_invalid("PLAYBOOK_FOUND sem playbook estruturado.")
        playbook_id = playbook.get("playbook_id")
        playbook_version = playbook.get("playbook_version")
        if not isinstance(playbook_id, str) or not playbook_id.strip():
            _evidence_invalid("PLAYBOOK_FOUND sem playbook_id.")
        if type(playbook_version) is not int or playbook_version <= 0:
            _evidence_invalid("PLAYBOOK_FOUND sem playbook_version valido.")
        record = OutcomeRecord(
            interaction_id=interaction_id,
            system=triage.system,
            intent=triage.intent,
            capability="",
            area=area,
            knowledge_id=knowledge_id,
            playbook_id=playbook_id,
            playbook_version=playbook_version,
            step_id="",
            outcome="GUIDED_BY_PLAYBOOK",
            reason_code="PLAYBOOK_FOUND",
        )
        validate_outcome_record(record)
        return record

    @staticmethod
    def from_request(
        interaction_id: str,
        record: AccessRequestRecord,
        assignment: RoutingAssignment | None = None,
    ) -> OutcomeRecord:
        validate_access_request_record(record)
        state = record.state
        if state == "PENDING_APPROVAL":
            if (
                type(assignment) is not RoutingAssignment
                or assignment.request_id != record.request_id
                or assignment.system != record.context.system
                or assignment.capability != record.context.capability
            ):
                _evidence_invalid("PENDING_APPROVAL exige RoutingAssignment compativel.")
            outcome = "ROUTED_TO_HUMAN"
            reason_code = "ROUTED_TO_HUMAN"
        elif state == "APPROVED":
            outcome = "APPROVED"
            reason_code = "APPROVED"
        elif state == "REJECTED":
            outcome = "REJECTED"
            reason_code = "REJECTED"
        elif state == "DENIED_POLICY":
            outcome = "DENIED_POLICY"
            reason_code = record.latest_policy.reason_code
        elif state == "COMPLETED":
            outcome = "EXECUTION_COMPLETED"
            reason_code = record.execution_result_code or ""
        elif state == "FAILED":
            outcome = "EXECUTION_FAILED"
            reason_code = record.execution_error_code or ""
        else:
            _evidence_invalid("State do request nao representa outcome analitico estavel.")

        context = record.context
        outcome_record = OutcomeRecord(
            interaction_id=interaction_id,
            system=context.system,
            intent=context.intent,
            capability=context.capability,
            area=context.requester.area,
            knowledge_id=context.knowledge_id,
            playbook_id=context.playbook_id,
            playbook_version=context.playbook_version,
            step_id=context.step_id,
            outcome=outcome,
            reason_code=reason_code,
        )
        validate_outcome_record(outcome_record)
        return outcome_record


class PatternAggregator:
    @staticmethod
    def aggregate(records: tuple[OutcomeRecord, ...]) -> tuple[PatternAggregate, ...]:
        grouped: dict[PatternKey, list[OutcomeRecord]] = defaultdict(list)
        for record in records:
            validate_outcome_record(record)
            key = PatternKey(record.system, record.intent, record.capability, record.area)
            grouped[key].append(record)

        patterns: list[PatternAggregate] = []
        for key in sorted(grouped):
            rows = grouped[key]
            outcomes = Counter(row.outcome for row in rows)
            patterns.append(
                PatternAggregate(
                    key=key,
                    occurrence_count=len(rows),
                    evidence_ids=tuple(sorted(row.interaction_id for row in rows)),
                    outcome_counts=tuple(sorted(outcomes.items())),
                    knowledge_count=sum(bool(row.knowledge_id) for row in rows),
                    knowledge_ids=tuple(
                        sorted({row.knowledge_id for row in rows if row.knowledge_id})
                    ),
                    playbook_count=sum(bool(row.playbook_id) for row in rows),
                    playbook_ids=tuple(
                        sorted({row.playbook_id for row in rows if row.playbook_id})
                    ),
                    reason_codes=tuple(
                        sorted({row.reason_code for row in rows if row.reason_code})
                    ),
                )
            )
        return tuple(patterns)


def _opportunity_id(category: str, key: PatternKey) -> str:
    payload = {
        "category": category,
        "key": {
            "area": key.area,
            "capability": key.capability,
            "intent": key.intent,
            "system": key.system,
        },
    }
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16].upper()
    return f"OPP-{digest}"


class OpportunityEngine:
    def generate(
        self,
        patterns: tuple[PatternAggregate, ...],
    ) -> tuple[PreventionOpportunity, ...]:
        opportunities: list[PreventionOpportunity] = []
        for pattern in patterns:
            if pattern.occurrence_count < MIN_RECURRENCE:
                continue

            outcomes = dict(pattern.outcome_counts)
            all_human = outcomes.get("ROUTED_TO_HUMAN", 0) == pattern.occurrence_count
            categories: set[str] = {"PREVENTION_CANDIDATE"}

            if all_human:
                categories.add("HUMAN_DEPENDENCY")
                if pattern.knowledge_count == 0:
                    categories.add("KNOWLEDGE_GAP")
                elif (
                    pattern.knowledge_count == pattern.occurrence_count
                    and pattern.playbook_count == 0
                ):
                    categories.add("PLAYBOOK_GAP")
                if (
                    pattern.key.capability
                    and pattern.playbook_count == pattern.occurrence_count
                    and len(pattern.playbook_ids) == 1
                ):
                    categories.add("AUTOMATION_CANDIDATE")

            if outcomes.get("EXECUTION_FAILED", 0) >= MIN_RECURRENCE:
                categories.add("EXECUTION_RELIABILITY_ISSUE")

            for category in sorted(categories):
                opportunities.append(
                    PreventionOpportunity(
                        opportunity_id=_opportunity_id(category, pattern.key),
                        category=category,
                        key=pattern.key,
                        occurrence_count=pattern.occurrence_count,
                        evidence_ids=pattern.evidence_ids,
                        reason_codes=pattern.reason_codes,
                    )
                )

        return tuple(
            sorted(
                opportunities,
                key=lambda item: (item.key, item.category, item.opportunity_id),
            )
        )
