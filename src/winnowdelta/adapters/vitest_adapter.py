"""Vitest adapter (Feature #1).

Runs ``vitest run --reporter=json --outputFile=<tmp>`` and parses via the shared
Jest/Vitest JSON parser. Defaults to ``npx vitest run`` so the appended reporter
flags reach vitest directly (an ``npm run test`` wrapper would swallow them);
the runner routes ``npx`` through ComSpec on Windows.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

from ..core import jest_json
from ..core.adapter import register
from ..core.config import Subproject
from ..core.model import NormalizedRun
from . import _support


class VitestAdapter:
    stack = "vitest"
    command_kind = "test"

    def _base_command(self, sub: Subproject) -> list[str]:
        return sub.command("test") or ["npx", "vitest", "run"]

    def collect(
        self,
        sub: Subproject,
        cwd: Path,
        timeout: float | None = None,
        selection: list[str] | None = None,
    ) -> NormalizedRun:
        base = self._base_command(sub)
        sel = list(selection) if selection else []
        return _support.collect_via_report(
            command="test",
            cwd=cwd,
            report_name="vitest.json",
            build_argv=lambda report: [
                *base,
                *sel,
                "--reporter=json",
                "--outputFile",
                str(report),
            ],
            parse_text=partial(jest_json.parse_jest_json, command="test", base=cwd),
            timeout=timeout,
        )


register(VitestAdapter())
