"""TypeScript typecheck adapter (Feature #2, build kind).

Runs ``tsc`` and parses ``file(line,col): error TSxxxx: msg`` diagnostics. The
invocation is chosen by sniffing the ``tsconfig.json`` in the subproject's cwd:

* **Flat project** → ``tsc --noEmit --pretty false``: type-checks in place, emits
  nothing.
* **Composite / project-references project** (``tsconfig`` has a non-empty
  ``references`` array or ``composite: true``) → ``tsc -b --pretty false``. Plain
  ``tsc`` *ignores* project references, so against a solution-style root
  (``files: []`` + ``references``) it type-checks nothing and reports a
  false-clean; only build mode (``tsc -b``) walks the reference graph. Build mode
  emits ``.tsbuildinfo`` + declarations as a side effect and is portable across
  TypeScript versions; override ``build`` in ``winnowdelta.toml`` to customize
  (e.g. add ``--noEmit`` on TypeScript >= 5.6, which allows it in build mode).

Clean projects exit 0 with no output; type errors exit non-zero with parseable
lines. A non-zero exit with *no* parseable diagnostics (bad tsconfig / tsc
missing) is surfaced as an error.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core import diagnostics
from ..core.adapter import register_diagnostic
from ..core.config import Subproject
from ..core.model import NormalizedRun
from . import _diag

# A non-empty ``"references": [ { ... } ]`` array or ``"composite": true`` marks a
# project that must be driven through ``tsc -b``. tsconfig is JSONC (comments,
# trailing commas), so a strict JSON parse would choke — sniff the raw text.
_PROJECT_REFERENCES_RE = re.compile(r'"references"\s*:\s*\[\s*\{')
_COMPOSITE_RE = re.compile(r'"composite"\s*:\s*true')


def _uses_project_references(cwd: Path) -> bool:
    """True when the ``tsconfig.json`` in *cwd* is composite / solution-style."""
    try:
        text = (cwd / "tsconfig.json").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(_PROJECT_REFERENCES_RE.search(text) or _COMPOSITE_RE.search(text))


class TscAdapter:
    tool = "tsc"
    command_kind = "build"

    def _base_command(self, sub: Subproject, cwd: Path) -> list[str]:
        override = sub.command("build")
        if override is not None:
            return override
        if _uses_project_references(cwd):
            # Build mode follows project references; plain --noEmit would not.
            return ["npx", "tsc", "-b", "--pretty", "false"]
        return ["npx", "tsc", "--noEmit", "--pretty", "false"]

    def collect(
        self, sub: Subproject, cwd: Path, timeout: float | None = None
    ) -> NormalizedRun:
        return _diag.run_diagnostics(
            command="build",
            cwd=cwd,
            argv=self._base_command(sub, cwd),
            parse=lambda r: diagnostics.parse_tsc(
                "\n".join([r.stdout, r.stderr]), base=cwd
            ),
            # tsc emits diagnostics to stdout; a non-zero exit with none parsed
            # means an invocation/config failure, not a clean run.
            is_error=lambda r, d: bool(not d and r.exit_code != 0),
            timeout=timeout,
        )


register_diagnostic(TscAdapter())
