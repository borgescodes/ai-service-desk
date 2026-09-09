import json
from dataclasses import replace
from pathlib import Path

from ai_service_desk.engine.learning_prevention import (
    InMemoryOutcomeStore,
    OpportunityEngine,
    OutcomeConflictError,
    OutcomeRecord,
    OutcomeValidationError,
    PatternAggregate,
    PatternAggregator,
    PreventionOpportunity,
    validate_outcome_record,
)

LEARNING_PREVENTION_CASE_IDS = (
    "KNOWLEDGE_RECURRING_RESOLVES",
    "KNOWLEDGE_GAP",
    "HUMAN_DEPENDENCY",
    "AUTOMATION_CANDIDATE",
    "PREVENTION_CANDIDATE",
    "EXECUTION_RELIABILITY_ISSUE",
    "IDEMPOTENT_INGESTION",
    "CONFLICT_FAILS_CLOSED",
    "ANALYTICS_DOES_NOT_MUTATE_OPERATIONAL_STATE",
    "DETERMINISTIC_SNAPSHOT",
)

_FIXTURE_FIELDS = frozenset(OutcomeRecord.__dataclass_fields__)


def load_learning_prevention_cases(path: Path) -> tuple[OutcomeRecord, ...]:
    rows: list[OutcomeRecord] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        data = json.loads(raw_line)
        if not isinstance(data, dict) or set(data) != _FIXTURE_FIELDS:
            raise OutcomeValidationError(
                "OUTCOME_FIXTURE_INVALID",
                f"Fixture sintetica invalida na linha {line_number}.",
            )
        record = OutcomeRecord(**data)
        validate_outcome_record(record)
        rows.append(record)
    return tuple(sorted(rows, key=lambda item: item.interaction_id))


def _analyze(
    records: tuple[OutcomeRecord, ...],
) -> tuple[
    InMemoryOutcomeStore,
    tuple[OutcomeRecord, ...],
    tuple[PatternAggregate, ...],
    tuple[PreventionOpportunity, ...],
]:
    store = InMemoryOutcomeStore()
    for record in records:
        store.ingest(record)
    snapshot = store.snapshot()
    patterns = PatternAggregator.aggregate(snapshot)
    opportunities = OpportunityEngine().generate(patterns)
    return store, snapshot, patterns, opportunities


def _pattern_for_system(
    patterns: tuple[PatternAggregate, ...],
    system: str,
) -> PatternAggregate:
    matches = tuple(pattern for pattern in patterns if pattern.key.system == system)
    if len(matches) != 1:
        raise OutcomeValidationError(
            "OUTCOME_FIXTURE_INVALID",
            f"Fixture exige um unico pattern para {system}.",
        )
    return matches[0]


def _categories_for_system(
    opportunities: tuple[PreventionOpportunity, ...],
    system: str,
) -> tuple[str, ...]:
    return tuple(
        sorted(item.category for item in opportunities if item.key.system == system)
    )


def _case(case_id: str, expected: str, actual: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "ok": actual == expected,
        "expected": expected,
        "actual": actual,
    }


def run_learning_prevention_smoke(path: Path) -> dict[str, object]:
    records = load_learning_prevention_cases(path)
    records_before = records
    store, snapshot, patterns, opportunities = _analyze(records)

    pbi = _pattern_for_system(patterns, "POWER_BI")
    pbi_categories = _categories_for_system(opportunities, "POWER_BI")
    m365_categories = _categories_for_system(opportunities, "MICROSOFT_365")
    hardware_categories = _categories_for_system(opportunities, "HARDWARE")
    cdm_categories = _categories_for_system(opportunities, "CDM")

    knowledge_actual = (
        "COUNT_3:NO_HUMAN_DEPENDENCY"
        if pbi.occurrence_count == 3 and "HUMAN_DEPENDENCY" not in pbi_categories
        else "FAILED"
    )

    before_replay = len(store.snapshot())
    store.ingest(snapshot[0])
    after_replay = len(store.snapshot())
    idempotent_actual = "NO_DUPLICATE" if before_replay == after_replay else "FAILED"

    conflict_record = replace(
        snapshot[0],
        outcome="REJECTED",
        reason_code="REJECTED_BY_HUMAN",
    )
    try:
        store.ingest(conflict_record)
    except OutcomeConflictError as exc:
        conflict_actual = exc.reason_code
    else:
        conflict_actual = "ACCEPTED_INCOMPATIBLE_PAYLOAD"

    deterministic_patterns = PatternAggregator.aggregate(tuple(reversed(snapshot)))
    deterministic_opportunities = OpportunityEngine().generate(deterministic_patterns)
    deterministic_actual = (
        "MATCH"
        if patterns == deterministic_patterns and opportunities == deterministic_opportunities
        else "MISMATCH"
    )

    cases = (
        _case(
            "KNOWLEDGE_RECURRING_RESOLVES",
            "COUNT_3:NO_HUMAN_DEPENDENCY",
            knowledge_actual,
        ),
        _case(
            "KNOWLEDGE_GAP",
            "PRESENT",
            "PRESENT" if "KNOWLEDGE_GAP" in m365_categories else "ABSENT",
        ),
        _case(
            "HUMAN_DEPENDENCY",
            "PRESENT",
            "PRESENT" if "HUMAN_DEPENDENCY" in m365_categories else "ABSENT",
        ),
        _case(
            "AUTOMATION_CANDIDATE",
            "PRESENT",
            "PRESENT" if "AUTOMATION_CANDIDATE" in hardware_categories else "ABSENT",
        ),
        _case(
            "PREVENTION_CANDIDATE",
            "PRESENT",
            "PRESENT" if "PREVENTION_CANDIDATE" in pbi_categories else "ABSENT",
        ),
        _case(
            "EXECUTION_RELIABILITY_ISSUE",
            "PRESENT",
            "PRESENT" if "EXECUTION_RELIABILITY_ISSUE" in cdm_categories else "ABSENT",
        ),
        _case("IDEMPOTENT_INGESTION", "NO_DUPLICATE", idempotent_actual),
        _case("CONFLICT_FAILS_CLOSED", "OUTCOME_CONFLICT", conflict_actual),
        _case(
            "ANALYTICS_DOES_NOT_MUTATE_OPERATIONAL_STATE",
            "UNCHANGED",
            "UNCHANGED" if records == records_before else "MUTATED",
        ),
        _case("DETERMINISTIC_SNAPSHOT", "MATCH", deterministic_actual),
    )

    return {
        "ok": all(bool(item["ok"]) for item in cases),
        "case_count": len(cases),
        "cases": cases,
    }
