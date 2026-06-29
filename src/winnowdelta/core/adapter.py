"""Adapter protocol + registry.

An adapter is the per-framework knowledge: how to invoke the tool with its
machine reporter, and how to turn the raw ``ExecResult`` into a
``NormalizedRun``. Adapters are registered by ``stack`` name (matching
``Subproject.stack`` / ``config.detect_stack``); the core looks one up and stays
framework-agnostic.

Concrete adapters land starting in Phase 2 (pytest first).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .config import Subproject
from .model import NormalizedRun
from .runner import ExecResult


@runtime_checkable
class Adapter(Protocol):
    #: Stack key this adapter handles (e.g. "pytest", "vitest", "django").
    stack: str

    def build_command(self, sub: Subproject) -> list[str]:
        """Argv to run, including the framework's machine-reporter flags."""
        ...

    def parse(self, result: ExecResult, sub: Subproject) -> NormalizedRun:
        """Turn raw process output into the filtered, normalized delta."""
        ...


_REGISTRY: dict[str, Adapter] = {}


def register(adapter: Adapter) -> None:
    _REGISTRY[adapter.stack] = adapter


def get(stack: str) -> Adapter | None:
    return _REGISTRY.get(stack)


def stacks() -> list[str]:
    return sorted(_REGISTRY)
