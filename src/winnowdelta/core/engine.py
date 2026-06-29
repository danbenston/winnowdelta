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
from .model import NormalizedRun


def run_test(
    root: str | Path,
    subproject: str | None = None,
    timeout: float | None = None,
) -> NormalizedRun:
    try:
        cfg = config.resolve(root)
    except config.ConfigError as exc:
        return NormalizedRun.errored("test", str(exc))
    if cfg is None:
        return NormalizedRun.errored(
            "test", "no winnowdelta.toml found and could not autodetect a stack"
        )

    try:
        sub = cfg.get(subproject)
    except config.ConfigError as exc:
        return NormalizedRun.errored("test", str(exc))

    adp = registry.get(sub.stack)
    if adp is None:
        known = ", ".join(registry.stacks()) or "none"
        return NormalizedRun.errored(
            "test", f"no test adapter for stack {sub.stack!r} (have: {known})"
        )

    cwd = sub.resolve_cwd(root)
    return adp.collect(sub, cwd, timeout)
