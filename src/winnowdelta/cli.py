"""Command-line entry point for winnowdelta.

Phase 0: establishes the CLI surface (``--help`` / ``--version`` and a stub
``test`` subcommand that emits the empty-but-valid output envelope). Adapters
and real execution arrive in later phases.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import __version__

SCHEMA_VERSION = "0.0.1"


def _empty_envelope(command: str) -> dict[str, object]:
    """Return the minimal valid output envelope.

    This is the stable contract every command emits; later phases fill in the
    ``failures`` / ``diagnostics`` payloads.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": "ok",
        "failures": [],
        "diagnostics": [],
    }


def _cmd_test(args: argparse.Namespace) -> int:
    print(json.dumps(_empty_envelope("test"), indent=2))
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
