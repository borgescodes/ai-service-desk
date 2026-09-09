import sys

from ai_service_desk import cli, phase9_cli

argv = sys.argv[1:]
if phase9_cli.handles(argv):
    raise SystemExit(phase9_cli.main(argv))

raise SystemExit(cli.main(argv))
