import argparse
from pathlib import Path

from ai_service_desk.engine.learning_prevention_smoke import run_learning_prevention_smoke

PHASE11_COMMANDS = frozenset({"learning-prevention-smoke"})


def handles(argv: list[str]) -> bool:
    return bool(argv) and argv[0] in PHASE11_COMMANDS


def _fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "phase11_learning_prevention_cases.jsonl"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-service-desk")
    parser.add_argument("command", choices=sorted(PHASE11_COMMANDS))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "learning-prevention-smoke":
        return 2

    report = run_learning_prevention_smoke(_fixture_path())
    if not report["ok"]:
        return 1

    print("LEARNING PREVENTION SMOKE OK")
    print(f"Casos sinteticos: {report['case_count']}")
    return 0
