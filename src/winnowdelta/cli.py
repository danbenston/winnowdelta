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


def _cmd_check(args: argparse.Namespace) -> int:
    run = engine.run_check(
        Path.cwd(),
        subproject=args.subproject,
        kind=args.kind,
        timeout=args.timeout,
        use_baseline=not args.all,
    )
    return _emit(run, args.text)


def _cmd_baseline(args: argparse.Namespace) -> int:
    if args.action == "clear":
        cleared = engine.clear_baseline(Path.cwd(), subproject=args.subproject)
        print("baseline cleared" if cleared else "no baseline to clear")
        return 0

    run = engine.capture_baseline(Path.cwd(), subproject=args.subproject, timeout=args.timeout)
    if run.status is Status.ERROR:
        print(output.to_text(run))
        return _EXIT[Status.ERROR]
    print(f"captured {run.summary.total} baseline diagnostic(s)")
    return 0


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

    p_check = sub.add_parser(
        "check", help="Run build/lint tools; report only diagnostics new vs baseline."
    )
    p_check.add_argument("subproject", nargs="?", help="Configured subproject to run.")
    p_check.add_argument(
        "--kind", choices=["lint", "build"], default=None,
        help="Limit to lint or build tools (default: both).",
    )
    p_check.add_argument(
        "--all", action="store_true",
        help="Report all current diagnostics, ignoring the baseline.",
    )
    p_check.add_argument("--text", action="store_true", help="Human-readable output.")
    p_check.add_argument("--timeout", type=float, default=None, help="Kill after N seconds.")
    p_check.set_defaults(func=_cmd_check)

    p_base = sub.add_parser("baseline", help="Capture or clear the diagnostics baseline.")
    p_base.add_argument("action", choices=["capture", "clear"])
    p_base.add_argument("subproject", nargs="?", help="Configured subproject.")
    p_base.add_argument("--timeout", type=float, default=None, help="Kill after N seconds.")
    p_base.set_defaults(func=_cmd_baseline)

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
