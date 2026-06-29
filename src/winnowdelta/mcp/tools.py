"""MCP tool implementations — pure functions over the engine.

Kept free of any ``mcp`` import so they are unit-testable without the SDK
installed. ``server.py`` registers these with FastMCP. Every tool returns the
same versioned envelope the CLI emits (``output.to_envelope``), so an agent
gets byte-for-byte the same filtered delta regardless of surface.
"""

from __future__ import annotations

import os

from ..core import engine, output


def _root(root: str | None) -> str:
    return root or os.getcwd()


def run_tests(
    root: str | None = None,
    subproject: str | None = None,
    timeout: float | None = None,
    selection: list[str] | None = None,
    full: bool = False,
) -> dict[str, object]:
    """Run the test suite and return only the failures.

    *selection* limits the run to those runner-native test IDs (the affected-
    tests list, e.g. from codegraft); *full* ignores it and runs everything.
    """
    sel = None if full else selection
    run = engine.run_test(_root(root), subproject=subproject, timeout=timeout, selection=sel)
    return output.to_envelope(run)


def build_lint_delta(
    root: str | None = None,
    subproject: str | None = None,
    kind: str | None = None,
    timeout: float | None = None,
    all: bool = False,
) -> dict[str, object]:
    """Run build/lint tools and return only diagnostics new vs the baseline.

    *kind* limits to "lint" or "build"; *all* reports every current diagnostic,
    ignoring the baseline.
    """
    run = engine.run_check(
        _root(root),
        subproject=subproject,
        kind=kind,
        timeout=timeout,
        use_baseline=not all,
    )
    return output.to_envelope(run)


def capture_baseline(
    root: str | None = None,
    subproject: str | None = None,
    timeout: float | None = None,
) -> dict[str, object]:
    """Snapshot current build/lint diagnostics as the baseline to diff against."""
    run = engine.capture_baseline(_root(root), subproject=subproject, timeout=timeout)
    return output.to_envelope(run)


def clear_baseline(root: str | None = None, subproject: str | None = None) -> dict[str, object]:
    """Delete the stored baseline for a subproject."""
    cleared = engine.clear_baseline(_root(root), subproject=subproject)
    return {"cleared": cleared}
