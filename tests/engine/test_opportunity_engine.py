from dataclasses import replace

from ai_service_desk.engine.learning_prevention import (
    MIN_RECURRENCE,
    OPPORTUNITY_CATEGORIES,
    OpportunityEngine,
    OutcomeRecord,
    PatternAggregator,
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


def categories(rows: tuple[OutcomeRecord, ...]) -> tuple[str, ...]:
    patterns = PatternAggregator.aggregate(rows)
    return tuple(item.category for item in OpportunityEngine().generate(patterns))


def test_threshold_is_explicit_and_two_occurrences_produce_no_opportunity() -> None:
    assert MIN_RECURRENCE == 3
    assert (
        OpportunityEngine().generate(
            PatternAggregator.aggregate((record("INT-001"), record("INT-002")))
        )
        == ()
    )


def test_recurrent_knowledge_resolution_is_prevention_only() -> None:
    actual = categories((record("INT-001"), record("INT-002"), record("INT-003")))
    assert actual == ("PREVENTION_CANDIDATE",)
    assert "HUMAN_DEPENDENCY" not in actual


def test_human_pattern_without_knowledge_is_knowledge_gap_and_dependency() -> None:
    rows = tuple(
        record(
            f"INT-{index}",
            knowledge_id="",
            outcome="ROUTED_TO_HUMAN",
            reason_code="ROUTED_TO_HUMAN",
        )
        for index in range(1, 4)
    )
    assert categories(rows) == (
        "HUMAN_DEPENDENCY",
        "KNOWLEDGE_GAP",
        "PREVENTION_CANDIDATE",
    )


def test_human_pattern_with_knowledge_without_playbook_is_playbook_gap() -> None:
    rows = tuple(
        record(
            f"INT-{index}",
            outcome="ROUTED_TO_HUMAN",
            reason_code="ROUTED_TO_HUMAN",
        )
        for index in range(1, 4)
    )
    assert categories(rows) == (
        "HUMAN_DEPENDENCY",
        "PLAYBOOK_GAP",
        "PREVENTION_CANDIDATE",
    )


def test_stable_playbook_human_pattern_is_automation_candidate() -> None:
    rows = tuple(
        record(
            f"INT-{index}",
            playbook_id="PB-SYN-001",
            playbook_version=1,
            outcome="ROUTED_TO_HUMAN",
            reason_code="ROUTED_TO_HUMAN",
        )
        for index in range(1, 4)
    )
    assert categories(rows) == (
        "AUTOMATION_CANDIDATE",
        "HUMAN_DEPENDENCY",
        "PREVENTION_CANDIDATE",
    )


def test_partial_knowledge_does_not_become_false_gap() -> None:
    rows = (
        record("INT-001", outcome="ROUTED_TO_HUMAN", reason_code="ROUTED_TO_HUMAN"),
        record(
            "INT-002",
            knowledge_id="",
            outcome="ROUTED_TO_HUMAN",
            reason_code="ROUTED_TO_HUMAN",
        ),
        record("INT-003", outcome="ROUTED_TO_HUMAN", reason_code="ROUTED_TO_HUMAN"),
    )
    actual = categories(rows)
    assert "KNOWLEDGE_GAP" not in actual
    assert "PLAYBOOK_GAP" not in actual
    assert "HUMAN_DEPENDENCY" in actual


def test_partial_playbook_does_not_become_false_automation_candidate() -> None:
    rows = (
        record(
            "INT-001",
            playbook_id="PB-SYN-001",
            playbook_version=1,
            outcome="ROUTED_TO_HUMAN",
            reason_code="ROUTED_TO_HUMAN",
        ),
        record("INT-002", outcome="ROUTED_TO_HUMAN", reason_code="ROUTED_TO_HUMAN"),
        record("INT-003", outcome="ROUTED_TO_HUMAN", reason_code="ROUTED_TO_HUMAN"),
    )
    assert "AUTOMATION_CANDIDATE" not in categories(rows)


def test_execution_failures_create_reliability_issue() -> None:
    rows = tuple(
        record(
            f"INT-{index}",
            system="CDM",
            capability="CDM_ACCESS_REQUEST",
            playbook_id="PB-SYN-CDM",
            playbook_version=1,
            outcome="EXECUTION_FAILED",
            reason_code="CDM_INTERNAL_ERROR",
        )
        for index in range(1, 4)
    )
    assert categories(rows) == (
        "EXECUTION_RELIABILITY_ISSUE",
        "PREVENTION_CANDIDATE",
    )


def test_three_failures_with_one_success_still_create_reliability_issue() -> None:
    failed = tuple(
        record(
            f"INT-F-{index}",
            system="CDM",
            capability="CDM_ACCESS_REQUEST",
            playbook_id="PB-SYN-CDM",
            playbook_version=1,
            outcome="EXECUTION_FAILED",
            reason_code="CDM_INTERNAL_ERROR",
        )
        for index in range(1, 4)
    )
    success = record(
        "INT-S-001",
        system="CDM",
        capability="CDM_ACCESS_REQUEST",
        playbook_id="PB-SYN-CDM",
        playbook_version=1,
        outcome="EXECUTION_COMPLETED",
        reason_code="CDM_ACCESS_CREATED",
    )
    assert "EXECUTION_RELIABILITY_ISSUE" in categories(failed + (success,))


def test_opportunity_ids_and_order_are_deterministic() -> None:
    rows = tuple(
        record(
            f"INT-{index}",
            knowledge_id="",
            outcome="ROUTED_TO_HUMAN",
            reason_code="ROUTED_TO_HUMAN",
        )
        for index in range(1, 4)
    )
    patterns = PatternAggregator.aggregate(rows)
    first = OpportunityEngine().generate(patterns)
    second = OpportunityEngine().generate(tuple(reversed(patterns)))
    assert first == second
    assert tuple(item.category for item in first) == tuple(sorted(item.category for item in first))
    assert len({item.opportunity_id for item in first}) == len(first)
    for item in first:
        assert item.opportunity_id.startswith("OPP-")
        assert item.occurrence_count == 3
        assert item.evidence_ids == ("INT-1", "INT-2", "INT-3")


def test_category_contract_is_closed() -> None:
    assert OPPORTUNITY_CATEGORIES == (
        "KNOWLEDGE_GAP",
        "PLAYBOOK_GAP",
        "HUMAN_DEPENDENCY",
        "AUTOMATION_CANDIDATE",
        "PREVENTION_CANDIDATE",
        "EXECUTION_RELIABILITY_ISSUE",
    )
