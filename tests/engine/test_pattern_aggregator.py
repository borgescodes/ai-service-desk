from dataclasses import replace

import pytest

from ai_service_desk.engine.learning_prevention import (
    OutcomeRecord,
    OutcomeValidationError,
    PatternAggregator,
    PatternKey,
)


def record(interaction_id: str, **changes: object) -> OutcomeRecord:
    value = OutcomeRecord(
        interaction_id=interaction_id,
        system="POWER_BI",
        intent="PROBLEMA_ACESSO",
        capability="POWER_BI_SUPPORT_REQUEST",
        area="COMERCIAL",
        knowledge_id="KB-SYN-001",
        playbook_id="",
        playbook_version=None,
        step_id="",
        outcome="RESOLVED_BY_KNOWLEDGE",
        reason_code="KNOWLEDGE_FOUND",
    )
    return replace(value, **changes)


def test_aggregator_groups_by_exact_primary_key() -> None:
    rows = (
        record("INT-001"),
        record("INT-002", knowledge_id="KB-SYN-002"),
        record("INT-003", outcome="ROUTED_TO_HUMAN", reason_code="ROUTED_TO_HUMAN"),
    )
    patterns = PatternAggregator.aggregate(rows)
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.key == PatternKey(
        "POWER_BI",
        "PROBLEMA_ACESSO",
        "POWER_BI_SUPPORT_REQUEST",
        "COMERCIAL",
    )
    assert pattern.occurrence_count == 3
    assert pattern.evidence_ids == ("INT-001", "INT-002", "INT-003")
    assert pattern.outcome_counts == (
        ("RESOLVED_BY_KNOWLEDGE", 2),
        ("ROUTED_TO_HUMAN", 1),
    )
    assert pattern.knowledge_ids == ("KB-SYN-001", "KB-SYN-002")
    assert pattern.playbook_ids == ()
    assert pattern.reason_codes == ("KNOWLEDGE_FOUND", "ROUTED_TO_HUMAN")


def test_different_primary_dimension_creates_distinct_pattern() -> None:
    rows = (
        record("INT-001"),
        record("INT-002", area="FINANCEIRO"),
        record("INT-003", system="ERP", capability="ERP_SUPPORT_REQUEST"),
    )
    patterns = PatternAggregator.aggregate(rows)
    assert len(patterns) == 3
    assert tuple(pattern.key for pattern in patterns) == tuple(
        sorted(pattern.key for pattern in patterns)
    )


def test_knowledge_and_playbook_ids_do_not_split_primary_pattern() -> None:
    rows = (
        record("INT-001", knowledge_id="KB-A"),
        record(
            "INT-002",
            knowledge_id="KB-B",
            playbook_id="PB-B",
            playbook_version=2,
        ),
    )
    patterns = PatternAggregator.aggregate(rows)
    assert len(patterns) == 1
    assert patterns[0].knowledge_ids == ("KB-A", "KB-B")
    assert patterns[0].playbook_ids == ("PB-B",)


def test_empty_evidence_dimensions_are_excluded_from_sets() -> None:
    pattern = PatternAggregator.aggregate(
        (
            record(
                "INT-001",
                knowledge_id="",
                reason_code="",
                outcome="ROUTED_TO_HUMAN",
            ),
        )
    )[0]
    assert pattern.knowledge_ids == ()
    assert pattern.playbook_ids == ()
    assert pattern.reason_codes == ()


def test_same_records_in_different_order_produce_identical_aggregation() -> None:
    rows = (
        record("INT-003", system="ERP", capability="ERP_SUPPORT_REQUEST"),
        record("INT-001"),
        record("INT-002"),
    )
    assert PatternAggregator.aggregate(rows) == PatternAggregator.aggregate(tuple(reversed(rows)))


def test_invalid_record_fails_before_aggregation() -> None:
    invalid = record("INT-001", outcome="UNKNOWN")
    with pytest.raises(OutcomeValidationError) as captured:
        PatternAggregator.aggregate((invalid,))
    assert captured.value.reason_code == "OUTCOME_INVALID"
