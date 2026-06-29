"""Command-line entry point for winnowdelta.

The CLI is a thin wrapper over the core pipeline. As of Phase 1 the ``test``
command emits a real (still empty) ``NormalizedRun`` via the output emitter;
Phase 2 wires the pytest adapter behind it.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .core import engine, output
from .core.model import NormalizedRun, Status
from .core.output import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION", "build_parser", "main"]

# Process exit codes: 0 = clean, 1 = failures/diagnostics found, 2 = tool error.
_EXIT = {Status.OK: 0, Status.FAILED: 1, Status.ERROR: 2}


def _emit(run: NormalizedRun, as_text: bool) -> int:
    print(output.to_text(run) if as_text else output.to_json(run))
    return _EXIT[run.status]


def _cmd_test(args: argparse.Namespace) -> int:
    run = engine.run_test(Path.cwd(), subproject=args.subproject, timeout=args.timeout)
    return _emit(run, args.text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="winnowdelta",
        description="Run a project's tests/build/lint and return only the filtered delta.",
    )
    parser.add_argument("--version", action="version", version=f"winnowdelta {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_test = sub.add_parser("test", help="Run the test suite and report only failures.")
    p_test.add_argument("subproject", nargs="?", help="Configured subproject to run.")
    p_test.add_argument(
        "--text", action="store_true", help="Human-readable output instead of JSON."
    )
    p_test.add_argument(
        "--timeout", type=float, default=None, help="Kill the run after N seconds."
    )
    p_test.set_defaults(func=_cmd_test)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
