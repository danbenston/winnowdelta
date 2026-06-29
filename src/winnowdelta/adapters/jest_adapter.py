"""Jest adapter (Feature #1), including the ``jest-expo`` preset (meshimate).

Runs ``jest --json --outputFile=<tmp>`` and parses via the shared Jest/Vitest
JSON parser. The project's own jest config (e.g. the ``jest-expo`` preset)
governs collection; we only add reporting flags. ``--ci`` avoids writing new
snapshots, and ``--passWithNoTests`` keeps an empty run from being an error.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

from ..core import jest_json
from ..core.adapter import register
from ..core.config import Subproject
from ..core.model import NormalizedRun
from . import _support


class JestAdapter:
    stack = "jest"
    command_kind = "test"

    def _base_command(self, sub: Subproject) -> list[str]:
        return sub.command("test") or ["npx", "jest"]

    def collect(
        self, sub: Subproject, cwd: Path, timeout: float | None = None
    ) -> NormalizedRun:
        base = self._base_command(sub)
        return _support.collect_via_report(
            command="test",
            cwd=cwd,
            report_name="jest.json",
            build_argv=lambda report: [
                *base,
                "--ci",
                "--passWithNoTests",
                "--json",
                "--outputFile",
                str(report),
            ],
            parse_text=partial(jest_json.parse_jest_json, command="test", base=cwd),
            timeout=timeout,
        )


register(JestAdapter())
