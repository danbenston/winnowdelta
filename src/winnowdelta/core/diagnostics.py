"""Diagnostic parsers for the build/lint adapters (Feature #2).

Each returns a list of ``Diagnostic`` from a tool's raw output. Pure and
snapshot-testable. The baseline diff (``baseline.diff_diagnostics``) runs on
top of these.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .model import Diagnostic
from .paths import relativize

# tsc --pretty false:  src/foo.ts(12,5): error TS2322: Type 'x' is not ...
_TSC = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<col>\d+)\): "
    r"(?P<sev>error|warning) (?P<rule>TS\d+): (?P<msg>.*)$"
)


def parse_tsc(text: str, *, base: Path | None = None) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line in text.splitlines():
        m = _TSC.match(line.rstrip())
        if not m:
            continue  # continuation / unrelated lines
        diagnostics.append(
            Diagnostic(
                file=relativize(m["file"], base) or m["file"],
                line=int(m["line"]),
                col=int(m["col"]),
                rule=m["rule"],
                severity=m["sev"],
                message=m["msg"].strip(),
            )
        )
    return diagnostics


def parse_eslint_json(text: str, *, base: Path | None = None) -> list[Diagnostic]:
    """Parse ``eslint --format json`` output. Raises ValueError on bad JSON."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid ESLint JSON: {exc}") from exc

    diagnostics: list[Diagnostic] = []
    for file_entry in data if isinstance(data, list) else []:
        if not isinstance(file_entry, dict):
            continue
        file_path = file_entry.get("filePath")
        for msg in file_entry.get("messages", []):
            if not isinstance(msg, dict):
                continue
            severity = "error" if msg.get("severity") == 2 else "warning"
            diagnostics.append(
                Diagnostic(
                    file=relativize(file_path, base) or str(file_path),
                    line=msg.get("line"),
                    col=msg.get("column"),
                    rule=msg.get("ruleId"),
                    severity=severity,
                    message=str(msg.get("message", "")),
                )
            )
    return diagnostics


def parse_prettier_list(text: str, *, base: Path | None = None) -> list[Diagnostic]:
    """Parse ``prettier --list-different`` output (one unformatted file per line)."""
    diagnostics: list[Diagnostic] = []
    for line in text.splitlines():
        path = line.strip()
        if not path:
            continue
        diagnostics.append(
            Diagnostic(
                file=relativize(path, base) or path,
                severity="warning",
                rule="prettier",
                message="not formatted",
            )
        )
    return diagnostics
