"""Prettier adapter (Feature #2, lint kind).

Runs ``prettier --list-different .`` — one unformatted file path per line, exit
1 when any differ, 0 when clean, 2 on error. Each listed file becomes a
formatting diagnostic.
"""

from __future__ import annotations

from pathlib import Path

from ..core import diagnostics
from ..core.adapter import register_diagnostic
from ..core.config import Subproject
from ..core.model import NormalizedRun
from . import _diag


class PrettierAdapter:
    tool = "prettier"
    command_kind = "lint"

    def _base_command(self, sub: Subproject) -> list[str]:
        return ["npx", "prettier", "--list-different", "."]

    def collect(
        self, sub: Subproject, cwd: Path, timeout: float | None = None
    ) -> NormalizedRun:
        return _diag.run_diagnostics(
            command="lint",
            cwd=cwd,
            argv=self._base_command(sub),
            parse=lambda r: diagnostics.parse_prettier_list(r.stdout, base=cwd),
            # 0 = clean, 1 = differences found; anything else is a real failure.
            is_error=lambda r, d: r.exit_code not in (0, 1),
            timeout=timeout,
        )


register_diagnostic(PrettierAdapter())
