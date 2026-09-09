import sys

from ai_service_desk.cli import main as legacy_main
from ai_service_desk.phase9_cli import handles, main as phase9_main

argv = sys.argv[1:]
if handles(argv):
    raise SystemExit(phase9_main(argv))

raise SystemExit(legacy_main(argv))
