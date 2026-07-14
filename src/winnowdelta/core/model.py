"""Normalized result model — the single internal representation every adapter
parses into and every output surface renders from.

Adapters never emit JSON directly; they build these dataclasses, and
``output.py`` is the only thing that serializes them. That keeps the wire
contract in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Status(StrEnum):
    """Outcome of a winnowdelta run.

    ``OK``     — the command ran and reported no failures/new diagnostics.
    ``FAILED`` — the command ran and reported failures/new diagnostics.
    ``ERROR``  — winnowdelta could not run or parse the command (toolchain
                 missing, timeout, unparseable output). Distinct from FAILED so
                 an agent can tell "your code is broken" from "I broke".
    """

    OK = "ok"
    FAILED = "failed"
    ERROR = "error"


@dataclass(frozen=True)
class Failure:
    """A single failed test, compressed to the actionable minimum."""

    test_id: str
    file: str | None = None
    line: int | None = None
    message: str = ""
    expected: str | None = None
    received: str | None = None


@dataclass(frozen=True)
class Diagnostic:
    """A single build/lint diagnostic (one entry of a baseline delta)."""

    file: str
    severity: str
    message: str
    line: int | None = None
    col: int | None = None
    rule: str | None = None


@dataclass(frozen=True)
class Summary:
    """Coarse counts for the run (no per-test detail)."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass
class NormalizedRun:
    """The filtered delta for one command invocation."""

    command: str  # logical kind: "test" | "lint" | "build"
    status: Status
    failures: list[Failure] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    summary: Summary = field(default_factory=Summary)
    duration_s: float = 0.0
    error: str | None = None  # populated only when status is ERROR
    # The diagnostic tools that actually ran (check/baseline only) — e.g.
    # ["tsc", "eslint"]. This disambiguates an empty `diagnostics`: a non-empty
    # `checked` means "ran and clean"; an empty one means "nothing was checked"
    # (no matching tool for this kind, or none detected). Empty for test runs.
    checked: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls, command: str) -> NormalizedRun:
        """An OK run with no payload — the Phase 0 envelope, now typed."""
        return cls(command=command, status=Status.OK)

    @classmethod
    def errored(cls, command: str, error: str) -> NormalizedRun:
        return cls(command=command, status=Status.ERROR, error=error)
