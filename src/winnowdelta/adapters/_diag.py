"""Shared plumbing for diagnostic adapters (Feature #2).

Diagnostic tools (tsc, eslint, prettier) write to stdout rather than a report
file, so they don't use the report-file helper. This centralizes the run +
timeout handling and the NormalizedRun assembly.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..core import runner
from ..core.model import Diagnostic, NormalizedRun, Status, Summary


def tail(result: runner.ExecResult) -> str:
    """Why the tool failed, with its exit code — see ``runner.output_tail``."""
    return f"exit {result.exit_code}: {runner.output_tail(result)}"


def run_diagnostics(
    *,
    command: str,
    cwd: Path,
    argv: list[str],
    parse: Callable[[runner.ExecResult], list[Diagnostic]],
    is_error: Callable[[runner.ExecResult, list[Diagnostic]], bool],
    timeout: float | None,
) -> NormalizedRun:
    result = runner.run(argv, cwd=cwd, timeout=timeout)
    # Time spent is real even when the tool failed — the engine sums these into
    # the run's total, and dropping them under-reports a slow broken toolchain.
    if result.timed_out:
        return NormalizedRun.errored(
            command, f"{command} timed out after {timeout}s", duration_s=result.duration_s
        )

    try:
        diagnostics = parse(result)
    except ValueError as exc:
        return NormalizedRun.errored(
            command, f"{command}: {exc}; {tail(result)}", duration_s=result.duration_s
        )

    if is_error(result, diagnostics):
        return NormalizedRun.errored(
            command, f"{command}: {tail(result)}", duration_s=result.duration_s
        )

    status = Status.FAILED if diagnostics else Status.OK
    return NormalizedRun(
        command=command,
        status=status,
        diagnostics=diagnostics,
        summary=Summary(total=len(diagnostics), failed=len(diagnostics)),
        duration_s=result.duration_s,
    )
