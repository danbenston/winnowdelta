"""Orchestration: config + adapter registry → a NormalizedRun.

The thin seam the CLI and (later) the MCP server share. Resolves the subproject,
finds the adapter for its stack, runs it, and turns every foreseeable failure
(no config, unknown subproject, missing adapter) into an ERROR-status run rather
than an exception — callers always get a NormalizedRun to emit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

    try:
        return adp.collect(sub, cwd, timeout, selection)
    except Exception as exc:  # defensive: never leak an adapter crash to the caller
        return NormalizedRun.errored("test", f"{sub.stack} adapter failed: {exc!r}")


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


@dataclass
class _Sweep:
    """The result of running every applicable diagnostic tool once."""

    diagnostics: list[Diagnostic] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    #: Tools that executed successfully — the "what did I actually check"
    #: evidence that keeps an empty ``diagnostics`` from being ambiguous. A tool
    #: that ERRORs (missing toolchain, unparseable output) is NOT listed: it did
    #: not successfully check anything.
    ran: list[str] = field(default_factory=list)
    #: Wall time across every tool, including ones that errored. Summed rather
    #: than measured once so the figure survives per-tool isolation.
    duration_s: float = 0.0


def _collect_diagnostics(
    sub: Subproject, cwd: Path, kind: str | None, timeout: float | None
) -> _Sweep:
    sweep = _Sweep()
    for tool in _tools_for(sub, cwd, kind):
        adp = registry.get_diagnostic(tool)
        assert adp is not None  # _tools_for only returns registered tools
        try:
            run = adp.collect(sub, cwd, timeout)
        except Exception as exc:  # defensive: isolate one tool's crash
            sweep.errors.append(f"{tool}: adapter failed: {exc!r}")
            continue
        sweep.duration_s += run.duration_s
        if run.status is Status.ERROR:
            sweep.errors.append(f"{tool}: {run.error}")
        else:
            sweep.ran.append(tool)
            sweep.diagnostics.extend(run.diagnostics)
    return sweep


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
    False (``all=True``), the baseline is ignored and every current diagnostic is
    reported — the absolute "does this build/lint clean from scratch?" check,
    which returns nothing when clean. The returned run's ``checked`` names the
    tools that actually ran, so an empty diagnostics list is never ambiguous.
    """
    command = kind or "check"
    resolved = _resolve_subproject(command, root, subproject)
    if isinstance(resolved, NormalizedRun):
        return resolved
    sub, cwd = resolved

    sweep = _collect_diagnostics(sub, cwd, kind, timeout)

    if use_baseline:
        baseline = BaselineStore(root).load(sub.name)
        introduced = diff_diagnostics(sweep.diagnostics, baseline)
    else:
        introduced = sweep.diagnostics

    if sweep.errors and not introduced:
        return NormalizedRun.errored(
            command, "; ".join(sweep.errors), checked=sweep.ran, duration_s=sweep.duration_s
        )

    status = Status.FAILED if introduced else Status.OK
    return NormalizedRun(
        command=command,
        status=status,
        diagnostics=introduced,
        summary=Summary(total=len(introduced), failed=len(introduced)),
        duration_s=sweep.duration_s,
        error="; ".join(sweep.errors) or None,
        checked=sweep.ran,
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

    sweep = _collect_diagnostics(sub, cwd, None, timeout)
    if sweep.errors:
        # Refuse to record a partial baseline: the tools that did not run would
        # have their pre-existing diagnostics reported as newly introduced.
        return NormalizedRun.errored(
            "baseline", "; ".join(sweep.errors), checked=sweep.ran, duration_s=sweep.duration_s
        )

    BaselineStore(root).save(sub.name, sweep.diagnostics)
    return NormalizedRun(
        command="baseline",
        status=Status.OK,
        diagnostics=sweep.diagnostics,
        summary=Summary(total=len(sweep.diagnostics)),
        duration_s=sweep.duration_s,
        checked=sweep.ran,
    )


def clear_baseline(
    root: str | Path, subproject: str | None = None
) -> tuple[bool, str | None]:
    """Delete a subproject's baseline. Returns ``(cleared, error)``.

    The two failure modes are genuinely different and used to collapse into a
    bare ``False``: "there was no baseline" (fine, nothing to do) versus "the
    config is broken so we never found out" (worth reporting). Callers need to
    tell them apart to pick an exit code.
    """
    resolved = _resolve_subproject("baseline", root, subproject)
    if isinstance(resolved, NormalizedRun):
        return False, resolved.error
    sub, _cwd = resolved
    return BaselineStore(root).clear(sub.name), None
