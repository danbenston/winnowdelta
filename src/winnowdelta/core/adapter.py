"""Adapter protocol + registry.

An adapter is the per-framework knowledge: invoke a tool through its machine
reporter and turn the result into a ``NormalizedRun``. Each adapter owns its full
invocation (including any temp reporter file it needs), so the interface is a
single ``collect`` call rather than a build/parse split — the two halves share
too much state (the reporter artifact) to separate cleanly.

Adapters register by ``stack`` name (matching ``Subproject.stack`` /
``config.detect_stack``); the engine looks one up and stays framework-agnostic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .config import Subproject
from .model import NormalizedRun


@runtime_checkable
class Adapter(Protocol):
    #: Stack key this adapter handles (e.g. "pytest", "vitest", "django").
    stack: str
    #: Logical command kind this adapter produces ("test" | "lint" | "build").
    command_kind: str

    def collect(
        self, sub: Subproject, cwd: Path, timeout: float | None = None
    ) -> NormalizedRun:
        """Run the framework in *cwd* and return the filtered, normalized delta."""
        ...


@runtime_checkable
class DiagnosticAdapter(Protocol):
    """A build/lint tool that emits diagnostics (Feature #2).

    Unlike test adapters (one per stack), several diagnostic tools can apply to
    a single subproject (e.g. eslint + prettier + tsc), so these register by
    ``tool`` name rather than stack.
    """

    #: Tool key (e.g. "tsc", "eslint", "prettier").
    tool: str
    #: Logical command kind ("lint" | "build").
    command_kind: str

    def collect(
        self, sub: Subproject, cwd: Path, timeout: float | None = None
    ) -> NormalizedRun:
        """Run the tool in *cwd* and return its diagnostics (pre-baseline)."""
        ...


_REGISTRY: dict[str, Adapter] = {}
_DIAG_REGISTRY: dict[str, DiagnosticAdapter] = {}


def register(adapter: Adapter) -> None:
    _REGISTRY[adapter.stack] = adapter


def get(stack: str) -> Adapter | None:
    return _REGISTRY.get(stack)


def stacks() -> list[str]:
    return sorted(_REGISTRY)


def register_diagnostic(adapter: DiagnosticAdapter) -> None:
    _DIAG_REGISTRY[adapter.tool] = adapter


def get_diagnostic(tool: str) -> DiagnosticAdapter | None:
    return _DIAG_REGISTRY.get(tool)


def diagnostic_tools() -> list[str]:
    return sorted(_DIAG_REGISTRY)
