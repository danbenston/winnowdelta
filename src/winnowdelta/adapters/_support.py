"""Shared adapter plumbing: run a tool that writes a report file, then parse it.

Every test adapter follows the same shape — invoke a framework with a
machine-reporter flag pointing at a temp file, then hand the file's text to a
parser. This centralizes the temp-file lifecycle, timeout handling, and the
"no report produced" diagnosis so each adapter is just command + parser.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from ..core import runner
from ..core.model import NormalizedRun, Status


@contextmanager
def _temp_report(name: str) -> Iterator[Path]:
    tmpdir = Path(tempfile.mkdtemp(prefix="winnowdelta-"))
    try:
        yield tmpdir / name
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _diagnose(result: runner.ExecResult, command: str) -> str:
    tail = (result.stderr or result.stdout or "").strip().splitlines()
    detail = " ".join(tail[-3:]) if tail else f"exited {result.exit_code}"
    return f"{command}: produced no report (exit {result.exit_code}): {detail}"


def collect_via_report(
    *,
    command: str,
    cwd: Path,
    report_name: str,
    build_argv: Callable[[Path], list[str]],
    parse_text: Callable[[str], NormalizedRun],
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
    report_env_var: str | None = None,
    empty_ok_exit_codes: tuple[int, ...] = (),
) -> NormalizedRun:
    """Run a report-producing tool and parse the result.

    *build_argv* receives the temp report path and returns the full argv.
    *parse_text* receives the report file's text and returns a NormalizedRun.
    When *report_env_var* is set, the report path is passed to the tool via that
    environment variable instead of argv (Django's runner reads it from the
    environment). When the tool produces no report but exits with a code in
    *empty_ok_exit_codes* (e.g. pytest's "no tests"), that is treated as a clean
    empty run rather than an error.
    """
    with _temp_report(report_name) as report:
        run_env: dict[str, str] | None = dict(env) if env is not None else None
        if report_env_var is not None:
            run_env = dict(run_env or {})
            run_env[report_env_var] = str(report)
        result = runner.run(build_argv(report), cwd=cwd, env=run_env, timeout=timeout)

        if result.timed_out:
            return NormalizedRun.errored(command, f"{command} timed out after {timeout}s")

        if not report.exists() or report.stat().st_size == 0:
            if result.exit_code in empty_ok_exit_codes:
                return NormalizedRun(
                    command=command, status=Status.OK, duration_s=result.duration_s
                )
            return NormalizedRun.errored(command, _diagnose(result, command))

        run = parse_text(report.read_text(encoding="utf-8"))
        run.duration_s = result.duration_s
        return run
