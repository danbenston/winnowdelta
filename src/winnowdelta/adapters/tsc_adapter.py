"""TypeScript typecheck adapter (Feature #2, build kind).

Runs ``tsc --noEmit --pretty false`` and parses the plain ``file(line,col):
error TSxxxx: msg`` diagnostics. Clean projects exit 0 with no output; type
errors exit non-zero with parseable lines. A non-zero exit with *no* parseable
diagnostics (e.g. bad tsconfig / tsc missing) is surfaced as an error.
"""

from __future__ import annotations

from pathlib import Path

from ..core import diagnostics
from ..core.adapter import register_diagnostic
from ..core.config import Subproject
from ..core.model import NormalizedRun
from . import _diag


class TscAdapter:
    tool = "tsc"
    command_kind = "build"

    def _base_command(self, sub: Subproject) -> list[str]:
        return sub.command("build") or ["npx", "tsc", "--noEmit", "--pretty", "false"]

    def collect(
        self, sub: Subproject, cwd: Path, timeout: float | None = None
    ) -> NormalizedRun:
        return _diag.run_diagnostics(
            command="build",
            cwd=cwd,
            argv=self._base_command(sub),
            parse=lambda r: diagnostics.parse_tsc(
                "\n".join([r.stdout, r.stderr]), base=cwd
            ),
            # tsc emits diagnostics to stdout; a non-zero exit with none parsed
            # means an invocation/config failure, not a clean run.
            is_error=lambda r, d: bool(not d and r.exit_code != 0),
            timeout=timeout,
        )


register_diagnostic(TscAdapter())
