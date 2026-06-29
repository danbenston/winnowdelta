"""Serialization — the one place a ``NormalizedRun`` becomes bytes.

Two surfaces: a stable versioned JSON envelope (the machine contract) and a
compact human-readable text rendering. Bump ``SCHEMA_VERSION`` on any
incompatible change to the JSON shape.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from .model import Diagnostic, Failure, NormalizedRun

# Frozen v1 wire contract. Bump only on an incompatible change to the envelope.
SCHEMA_VERSION = "1.0"


def to_envelope(run: NormalizedRun) -> dict[str, object]:
    """The stable JSON-able dict every machine consumer reads."""
    return {
        "schema_version": SCHEMA_VERSION,
        "command": run.command,
        "status": run.status.value,
        "summary": asdict(run.summary),
        "failures": [asdict(f) for f in run.failures],
        "diagnostics": [asdict(d) for d in run.diagnostics],
        "duration_s": round(run.duration_s, 3),
        "error": run.error,
    }


def to_json(run: NormalizedRun, *, indent: int | None = 2) -> str:
    return json.dumps(to_envelope(run), indent=indent)


def _failure_line(f: Failure) -> str:
    loc = f.file or "?"
    if f.line is not None:
        loc = f"{loc}:{f.line}"
    head = f"FAIL {f.test_id}  ({loc})"
    parts = [head]
    if f.message:
        parts.append(f"  {f.message}")
    if f.expected is not None or f.received is not None:
        parts.append(f"  expected: {f.expected!r}")
        parts.append(f"  received: {f.received!r}")
    return "\n".join(parts)


def _diagnostic_line(d: Diagnostic) -> str:
    loc = d.file
    if d.line is not None:
        loc = f"{loc}:{d.line}" + (f":{d.col}" if d.col is not None else "")
    rule = f" [{d.rule}]" if d.rule else ""
    return f"{d.severity.upper()} {loc}{rule}  {d.message}"


def to_text(run: NormalizedRun) -> str:
    """Compact human rendering — empty payload yields a single status line."""
    lines: list[str] = []
    if run.status.value == "error":
        return f"ERROR ({run.command}): {run.error or 'unknown error'}"

    for f in run.failures:
        lines.append(_failure_line(f))
    for d in run.diagnostics:
        lines.append(_diagnostic_line(d))

    s = run.summary
    if run.command == "test":
        tail = f"{s.failed} failed, {s.passed} passed"
        if s.skipped:
            tail += f", {s.skipped} skipped"
        lines.append(tail + f"  ({run.status.value})")
    elif not lines:
        lines.append(f"no new diagnostics ({run.status.value})")

    return "\n".join(lines)
