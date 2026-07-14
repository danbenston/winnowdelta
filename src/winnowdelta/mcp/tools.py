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

    Default (``all=False``): reports only diagnostics you INTRODUCED since the
    captured baseline — the low-output mode for iterating on an existing tree.

    ``all=True``: ignore the baseline and report every CURRENT diagnostic.
    Despite "every", this **returns empty when the target is clean** — so it is
    the absolute "does this build/lint from scratch?" check. Use it for brand-new
    files or packages, where the default can't help (a clean new file and an
    unchecked one both show 0 new diagnostics). Caveat: in a tree that already
    has diagnostics, ``all=True`` returns all of them (noisy) — keep the default
    there.

    *kind* limits to "lint" or "build" (None runs both). Either way the returned
    envelope's ``checked`` lists the tools that actually ran (e.g. ["tsc",
    "eslint"]); an empty ``diagnostics`` with a non-empty ``checked`` means "ran
    and clean", while an empty ``checked`` means nothing was checked.
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
