from pathlib import Path

from ai_service_desk.engine import triage_smoke
from ai_service_desk.engine.triage_smoke import load_triage_cases, run_triage_smoke
from ai_service_desk.engine.types import TicketClassification

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "phase5_triage_conversations.jsonl"


class FakeClient:
    def chat(self, payload: dict) -> dict:
        return {}

    def close(self) -> None:
        pass


class FakeKnowledge:
    def __init__(self, *args, **kwargs):
        pass

    def available_systems(self, intent: str) -> tuple[str, ...]:
        return {
            "PROBLEMA_ACESSO": ("CIGAM", "SIAGRI"),
            "PROBLEMA_IMPRESSAO": ("",),
        }.get(intent, ())

    def search_classified(self, text: str, classification: TicketClassification) -> dict:
        if classification.intent == "PROBLEMA_IMPRESSAO":
            knowledge_id = "KB-SYN-PRINT-001"
        elif classification.system == "SIAGRI":
            knowledge_id = "KB-SYN-SIAGRI-ACCESS-001"
        else:
            knowledge_id = "KB-SYN-CIGAM-ACCESS-001"
        return {
            "status": "KNOWLEDGE_FOUND",
            "reason": "MATCH",
            "knowledge": {
                "knowledge_id": knowledge_id,
                "title": "synthetic",
                "answer": "approved literal",
                "system": classification.system,
                "intent": classification.intent,
                "version": 1,
            },
        }


def fake_classify(text: str, chat) -> TicketClassification:
    mapping = {
        "Nao consigo acessar.": TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9),
        "CIGAM": TicketClassification("OUTRO", "CIGAM", {}, 0.3),
        "Nao consigo acessar o CIGAM.": TicketClassification("PROBLEMA_ACESSO", "CIGAM", {}, 0.9),
        "CIGAM e SIAGRI estao sem acesso.": TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9),
        "SIAGRI": TicketClassification("OUTRO", "SIAGRI", {}, 0.3),
        "Nao e CIGAM, e SIAGRI.": TicketClassification("OUTRO", "", {}, 0.3),
        "O sistema XYZ esta sem acesso.": TicketClassification("PROBLEMA_ACESSO", "XYZ", {}, 0.8),
        "XYZ": TicketClassification("OUTRO", "XYZ", {}, 0.3),
        "O CIGAM fecha em uma rotina ficticia ainda em revisao.": TicketClassification(
            "ERRO_SISTEMA", "CIGAM", {}, 0.8
        ),
        "A impressora ficticia nao imprime.": TicketClassification(
            "PROBLEMA_IMPRESSAO", "", {}, 0.9
        ),
        "Preciso de ajuda.": TicketClassification("OUTRO", "", {}, 0.5),
        "Nao sei explicar.": TicketClassification("OUTRO", "", {}, 0.5),
    }
    return mapping[text]


def test_phase5_fixture_has_exact_ten_unique_synthetic_cases() -> None:
    cases = load_triage_cases(FIXTURE)
    assert len(cases) == 10
    assert len({case["case_name"] for case in cases}) == 10
    assert all(1 <= len(case["turns"]) <= 3 for case in cases)


def test_smoke_report_contains_only_safe_case_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(triage_smoke, "OllamaClient", lambda url: FakeClient())
    monkeypatch.setattr(triage_smoke, "LocalEmbedder", lambda client: object())
    monkeypatch.setattr(triage_smoke, "KnowledgeEngine", FakeKnowledge)
    monkeypatch.setattr(triage_smoke, "classify_ticket", fake_classify)

    report = run_triage_smoke("index", FIXTURE, tmp_path / "report.json")

    assert report["ok"] is True
    assert len(report["cases"]) == 10
    allowed = {
        "case_name",
        "expected_status",
        "actual_status",
        "reason",
        "expected_knowledge_id",
        "actual_knowledge_id",
        "turn_count",
        "clarification_count",
        "passed",
    }
    for case in report["cases"]:
        assert set(case) == allowed
        forbidden = {"message", "messages", "turns", "transcript", "answer", "ticket_id"}
        assert not (forbidden & set(case))
    assert report["privacy"] == {
        "raw_text_included": False,
        "approved_content_included": False,
        "corporate_data_included": False,
    }
