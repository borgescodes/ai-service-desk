import sys

from ai_service_desk import cli, phase9_cli, phase10_cli, phase11_cli

argv = sys.argv[1:]
if phase11_cli.handles(argv):
    raise SystemExit(phase11_cli.main(argv))
if phase10_cli.handles(argv):
    raise SystemExit(phase10_cli.main(argv))
if phase9_cli.handles(argv):
    raise SystemExit(phase9_cli.main(argv))

raise SystemExit(cli.main(argv))
