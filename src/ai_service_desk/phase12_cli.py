import argparse

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
COMMANDS = frozenset({"web-demo", "web-demo-smoke"})
DEMO_MODES = ("DETERMINISTIC", "LOCAL_AI")
DEFAULT_DEMO_MODE = "DETERMINISTIC"


def handles(argv: list[str]) -> bool:
    return bool(argv) and argv[0] in COMMANDS


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-service-desk")
    subparsers = parser.add_subparsers(dest="command", required=True)

    web_demo = subparsers.add_parser("web-demo")
    web_demo.add_argument("--host", default="127.0.0.1")
    web_demo.add_argument("--port", type=int, default=8000)
    web_demo.add_argument("--mode", choices=DEMO_MODES, default=DEFAULT_DEMO_MODE)

    subparsers.add_parser("web-demo-smoke")
    return parser


def run_web_demo(host: str, port: int, mode: str) -> None:
    from ai_service_desk.web.api import run_web_demo as run

    run(host=host, port=port, mode=mode)


def run_web_demo_smoke() -> dict:
    from ai_service_desk.web.smoke import run_web_demo_smoke as run

    return run()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "web-demo":
        if args.host not in LOOPBACK_HOSTS:
            _parser().error("web-demo aceita somente host loopback.")
        if not 1 <= args.port <= 65535:
            _parser().error("port deve estar entre 1 e 65535.")
        run_web_demo(args.host, args.port, args.mode)
        return 0

    report = run_web_demo_smoke()
    passed = sum(bool(case.get("passed")) for case in report.get("cases", []))
    total = len(report.get("cases", []))
    if report.get("ok"):
        print(f"WEB DEMO SMOKE OK {passed}/{total}")
        return 0
    print(f"WEB DEMO SMOKE FAILED {passed}/{total}")
    return 1
