"""Orchestration: config + adapter registry → a NormalizedRun.

The thin seam the CLI and (later) the MCP server share. Resolves the subproject,
finds the adapter for its stack, runs it, and turns every foreseeable failure
(no config, unknown subproject, missing adapter) into an ERROR-status run rather
than an exception — callers always get a NormalizedRun to emit.
"""

from __future__ import annotations

from pathlib import Path

from .. import adapters  # noqa: F401  (registers built-in adapters)
from . import adapter as registry
from . import config
from .baseline import BaselineStore, diff_diagnostics
from .config import Subproject
from .model import Diagnostic, NormalizedRun, Status, Summary


def run_test(
    root: str | Path,
    subproject: str | None = None,
    timeout: float | None = None,
    selection: list[str] | None = None,
) -> NormalizedRun:
    """Run the test suite, optionally limited to an affected-tests *selection*.

    ``selection=None`` runs the whole suite (also the ``--full`` path). A
    provided-but-empty selection means "no tests are affected" and is a clean
    no-op — we skip invoking the runner entirely.
    """
    resolved = _resolve_subproject("test", root, subproject)
    if isinstance(resolved, NormalizedRun):
        return resolved
    sub, cwd = resolved

    adp = registry.get(sub.stack)
    if adp is None:
        known = ", ".join(registry.stacks()) or "none"
        return NormalizedRun.errored(
            "test", f"no test adapter for stack {sub.stack!r} (have: {known})"
        )

    if selection is not None and len(selection) == 0:
        # codegraft found no impacted tests — nothing to run.
        return NormalizedRun(command="test", status=Status.OK)

    return adp.collect(sub, cwd, timeout, selection)


def _tools_for(sub: Subproject, cwd: Path, kind: str | None) -> list[str]:
    """Diagnostic tools that apply to *sub*, filtered to *kind* if given."""
    candidates = list(sub.tools) if sub.tools else config.detect_diagnostic_tools(cwd)
    selected: list[str] = []
    for tool in candidates:
        adp = registry.get_diagnostic(tool)
        if adp is None:
            continue
        if kind is None or adp.command_kind == kind:
            selected.append(tool)
    return selected


def _collect_diagnostics(
    sub: Subproject, cwd: Path, kind: str | None, timeout: float | None
) -> tuple[list[Diagnostic], list[str]]:
    diagnostics: list[Diagnostic] = []
    errors: list[str] = []
    for tool in _tools_for(sub, cwd, kind):
        adp = registry.get_diagnostic(tool)
        assert adp is not None  # _tools_for only returns registered tools
        run = adp.collect(sub, cwd, timeout)
        if run.status is Status.ERROR:
            errors.append(f"{tool}: {run.error}")
        else:
            diagnostics.extend(run.diagnostics)
    return diagnostics, errors


def _resolve_subproject(
    command: str, root: str | Path, subproject: str | None
) -> tuple[Subproject, Path] | NormalizedRun:
    try:
        cfg = config.resolve(root)
    except config.ConfigError as exc:
        return NormalizedRun.errored(command, str(exc))
    if cfg is None:
        return NormalizedRun.errored(
            command, "no winnowdelta.toml found and could not autodetect a stack"
        )
    try:
        sub = cfg.get(subproject)
    except config.ConfigError as exc:
        return NormalizedRun.errored(command, str(exc))
    return sub, sub.resolve_cwd(root)


def run_check(
    root: str | Path,
    subproject: str | None = None,
    kind: str | None = None,
    timeout: float | None = None,
    use_baseline: bool = True,
) -> NormalizedRun:
    """Run build/lint tools and report only diagnostics new vs the baseline.

    *kind* limits to "lint" or "build"; None runs both. When *use_baseline* is
    False (``--all``), every current diagnostic is reported.
    """
    command = kind or "check"
    resolved = _resolve_subproject(command, root, subproject)
    if isinstance(resolved, NormalizedRun):
        return resolved
    sub, cwd = resolved

    current, errors = _collect_diagnostics(sub, cwd, kind, timeout)

    if use_baseline:
        baseline = BaselineStore(root).load(sub.name)
        introduced = diff_diagnostics(current, baseline)
    else:
        introduced = current

    if errors and not introduced:
        return NormalizedRun.errored(command, "; ".join(errors))

    status = Status.FAILED if introduced else Status.OK
    return NormalizedRun(
        command=command,
        status=status,
        diagnostics=introduced,
        summary=Summary(total=len(introduced), failed=len(introduced)),
        error="; ".join(errors) or None,
    )


def capture_baseline(
    root: str | Path,
    subproject: str | None = None,
    timeout: float | None = None,
) -> NormalizedRun:
    """Snapshot the current build/lint diagnostics as the baseline."""
    resolved = _resolve_subproject("baseline", root, subproject)
    if isinstance(resolved, NormalizedRun):
        return resolved
    sub, cwd = resolved

    current, errors = _collect_diagnostics(sub, cwd, None, timeout)
    if errors:
        return NormalizedRun.errored("baseline", "; ".join(errors))

    BaselineStore(root).save(sub.name, current)
    return NormalizedRun(
        command="baseline",
        status=Status.OK,
        diagnostics=current,
        summary=Summary(total=len(current)),
    )


def clear_baseline(root: str | Path, subproject: str | None = None) -> bool:
    resolved = _resolve_subproject("baseline", root, subproject)
    if isinstance(resolved, NormalizedRun):
        return False
    sub, _cwd = resolved
    return BaselineStore(root).clear(sub.name)
