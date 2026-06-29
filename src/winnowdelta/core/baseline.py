"""Baseline snapshot store + diagnostic delta (Feature #2).

The baseline is winnowdelta's *own* scratch state — a snapshot of the
build/lint diagnostics present before the agent's edits — kept under
``.winnowdelta/baseline/`` in the project. It is scoped to one edit cycle, not
cross-session project memory: capture before editing, then ``check`` reports
only diagnostics introduced since.

The diff is position-insensitive (fingerprint excludes line/column) and uses
multiset semantics, so shifting line numbers don't spuriously flag a
pre-existing warning as new, while a genuinely added second occurrence still
shows up.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .model import Diagnostic

BASELINE_DIR = Path(".winnowdelta") / "baseline"


def _fingerprint(d: Diagnostic) -> tuple[str, str | None, str, str]:
    return (d.file, d.rule, d.severity, d.message)


def diff_diagnostics(
    current: list[Diagnostic], baseline: list[Diagnostic]
) -> list[Diagnostic]:
    """Return the diagnostics in *current* not accounted for by *baseline*."""
    remaining = Counter(_fingerprint(d) for d in baseline)
    introduced: list[Diagnostic] = []
    for d in current:
        key = _fingerprint(d)
        if remaining.get(key, 0) > 0:
            remaining[key] -= 1
        else:
            introduced.append(d)
    return introduced


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


class BaselineStore:
    def __init__(self, root: str | Path) -> None:
        self.dir = Path(root) / BASELINE_DIR

    def _path(self, subproject: str) -> Path:
        return self.dir / f"{_sanitize(subproject)}.json"

    def exists(self, subproject: str) -> bool:
        return self._path(subproject).exists()

    def load(self, subproject: str) -> list[Diagnostic]:
        path = self._path(subproject)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [Diagnostic(**d) for d in data.get("diagnostics", [])]

    def save(self, subproject: str, diagnostics: list[Diagnostic]) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._path(subproject)
        payload = {
            "subproject": subproject,
            "captured_at": datetime.now(UTC).isoformat(),
            "diagnostics": [asdict(d) for d in diagnostics],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def clear(self, subproject: str) -> bool:
        path = self._path(subproject)
        if path.exists():
            path.unlink()
            return True
        return False
