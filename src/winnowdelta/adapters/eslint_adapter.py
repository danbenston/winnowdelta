"""ESLint adapter (Feature #2, lint kind).

Runs ``eslint . --format json`` and parses the JSON. ESLint exits 0 when clean
(or warnings-only) and 1 when there are lint errors, but we drive off the parsed
messages rather than the exit code. Non-JSON output (e.g. a config failure)
becomes an error via the parser raising ValueError.
"""

from __future__ import annotations

from pathlib import Path

from ..core import diagnostics
from ..core.adapter import register_diagnostic
from ..core.config import Subproject
from ..core.model import NormalizedRun
from . import _diag


class EslintAdapter:
    tool = "eslint"
    command_kind = "lint"

    def _base_command(self, sub: Subproject) -> list[str]:
        return sub.command("lint") or ["npx", "eslint", ".", "--format", "json"]

    def collect(
        self, sub: Subproject, cwd: Path, timeout: float | None = None
    ) -> NormalizedRun:
        return _diag.run_diagnostics(
            command="lint",
            cwd=cwd,
            argv=self._base_command(sub),
            parse=lambda r: diagnostics.parse_eslint_json(r.stdout, base=cwd),
            # Parser raises on bad JSON; exit code alone never means error here.
            is_error=lambda r, d: False,
            timeout=timeout,
        )


register_diagnostic(EslintAdapter())
