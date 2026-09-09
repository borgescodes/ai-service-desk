import argparse
import os
import sys
from pathlib import Path

from ai_service_desk.engine.cdm_integration_smoke import run_cdm_integration_smoke
from ai_service_desk.integrations.cdm import validate_service_token
from ai_service_desk.integrations.cdm_fake_api import serve_cdm_api

PHASE9_COMMANDS = frozenset({"cdm-api", "cdm-integration-smoke"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AI Service Desk: integracao local simulada do CDM."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    cdm_api = sub.add_parser("cdm-api")
    cdm_api.add_argument("--host", default="127.0.0.1")
    cdm_api.add_argument("--port", type=int, default=8765)

    cdm_smoke = sub.add_parser("cdm-integration-smoke")
    cdm_smoke.add_argument("--cases", type=Path, required=True)
    cdm_smoke.add_argument("--report", type=Path, required=True)
    return parser


def handles(argv: list[str]) -> bool:
    return bool(argv) and argv[0] in PHASE9_COMMANDS


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        token = validate_service_token(os.environ.get("CDM_API_TOKEN"))
        if args.command == "cdm-api":
            serve_cdm_api(args.host, args.port, token)
            return 0
        report = run_cdm_integration_smoke(args.cases, args.report, token)
        print(
            "CDM INTEGRATION SMOKE OK"
            if report["ok"]
            else "CDM INTEGRATION SMOKE REQUER REVISAO"
        )
        print(f"Casos sinteticos: {report['case_count']}")
        print("Relatorio agregado local: " + str(args.report))
        return 0 if report["ok"] else 1
    except KeyboardInterrupt:
        print("\nInterrompido.")
        return 130
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print("ERRO: " + str(exc), file=sys.stderr)
        return 1
