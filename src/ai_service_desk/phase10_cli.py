import argparse
import sys

from ai_service_desk.engine.routing_escalation_smoke import run_routing_escalation_smoke

PHASE10_COMMANDS = frozenset({"routing-escalation-smoke"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Service Desk: roteamento operacional local.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("routing-escalation-smoke")
    return parser


def handles(argv: list[str]) -> bool:
    return bool(argv) and argv[0] in PHASE10_COMMANDS


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command != "routing-escalation-smoke":
            return 1
        report = run_routing_escalation_smoke()
        print(
            "ROUTING ESCALATION SMOKE OK"
            if report["ok"]
            else "ROUTING ESCALATION SMOKE REQUER REVISAO"
        )
        print(f"Casos sinteticos: {report['case_count']}")
        return 0 if report["ok"] else 1
    except KeyboardInterrupt:
        print("\nInterrompido.")
        return 130
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print("ERRO: " + str(exc), file=sys.stderr)
        return 1
