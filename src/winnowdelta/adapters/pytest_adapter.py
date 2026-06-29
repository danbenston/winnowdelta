"""pytest adapter (Feature #1).

Runs the suite through pytest's built-in JUnit XML reporter — chosen over
pytest-json-report / pytest-reportlog because it needs *no* extra package in the
target project's environment, so it works against a repo as-is. The XML is
parsed by the shared ``core.junit`` parser.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

from ..core import junit, runner
from ..core.adapter import register
from ..core.config import Subproject
from ..core.model import NormalizedRun
from . import _support

# pytest exit code for "no tests collected" — not an error for our purposes.
_EXIT_NO_TESTS = 5


class PytestAdapter:
    stack = "pytest"
    command_kind = "test"

    def _base_command(self, sub: Subproject, cwd: Path) -> list[str]:
        configured = sub.command("test")
        if configured is not None:
            return configured
        python = runner.venv_python(cwd) or sys.executable
        return [python, "-m", "pytest"]

    def collect(
        self,
        sub: Subproject,
        cwd: Path,
        timeout: float | None = None,
        selection: list[str] | None = None,
    ) -> NormalizedRun:
        base = self._base_command(sub, cwd)
        sel = list(selection) if selection else []
        return _support.collect_via_report(
            command="test",
            cwd=cwd,
            report_name="report.xml",
            build_argv=lambda report: [
                *base,
                *sel,
                f"--junitxml={report}",
                "-p",
                "no:cacheprovider",
                "-o",
                "junit_logging=no",
                "-q",
            ],
            parse_text=partial(junit.parse_junit_xml, command="test", base=cwd),
            timeout=timeout,
            empty_ok_exit_codes=(_EXIT_NO_TESTS,),
        )


register(PytestAdapter())
