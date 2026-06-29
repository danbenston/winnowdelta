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


_REGISTRY: dict[str, Adapter] = {}


def register(adapter: Adapter) -> None:
    _REGISTRY[adapter.stack] = adapter


def get(stack: str) -> Adapter | None:
    return _REGISTRY.get(stack)


def stacks() -> list[str]:
    return sorted(_REGISTRY)
