"""pytest adapter (Feature #1).

Runs the suite through pytest's built-in JUnit XML reporter — chosen over
pytest-json-report / pytest-reportlog because it needs *no* extra package in the
target project's environment, so it works against a repo as-is. The XML is
parsed by the shared ``core.junit`` parser.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from ..core import junit, runner
from ..core.adapter import register
from ..core.config import Subproject
from ..core.model import NormalizedRun, Status

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
        self, sub: Subproject, cwd: Path, timeout: float | None = None
    ) -> NormalizedRun:
        tmpdir = Path(tempfile.mkdtemp(prefix="winnowdelta-pytest-"))
        report = tmpdir / "report.xml"
        argv = [
            *self._base_command(sub, cwd),
            f"--junitxml={report}",
            "-p",
            "no:cacheprovider",
            "-o",
            "junit_logging=no",
            "-q",
        ]
        try:
            result = runner.run(argv, cwd=cwd, timeout=timeout)

            if result.timed_out:
                return NormalizedRun.errored(
                    "test", f"pytest timed out after {timeout}s"
                )
            if not report.exists() or report.stat().st_size == 0:
                if result.exit_code == _EXIT_NO_TESTS:
                    return NormalizedRun(command="test", status=Status.OK,
                                         duration_s=result.duration_s)
                return NormalizedRun.errored("test", _diagnose(result))

            run = junit.parse_junit_xml(
                report.read_text(encoding="utf-8"),
                command="test",
                base=cwd,
                duration_s=result.duration_s,
            )
            return run
        finally:
            _cleanup(tmpdir)


def _diagnose(result: runner.ExecResult) -> str:
    """Best message for a run that produced no report (toolchain/collection error)."""
    tail = (result.stderr or result.stdout or "").strip().splitlines()
    detail = " ".join(tail[-3:]) if tail else f"pytest exited {result.exit_code}"
    return f"pytest produced no report (exit {result.exit_code}): {detail}"


def _cleanup(tmpdir: Path) -> None:
    import shutil

    shutil.rmtree(tmpdir, ignore_errors=True)


register(PytestAdapter())
