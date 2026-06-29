"""Django adapter (Feature #1) — the hard one.

``manage.py test`` has no native structured reporter, so we inject
``winnowdelta.django_runner.JUnitRunner`` (which needs no extra package in the
target venv) and read the JUnit XML it writes via the shared ``core.junit``
parser. winnowdelta's own source dir is placed on the subprocess ``PYTHONPATH``
so the project's interpreter can import the runner without installing
winnowdelta.
"""

from __future__ import annotations

import os
import sys
from functools import partial
from pathlib import Path

import winnowdelta

from ..core import junit, runner
from ..core.adapter import register
from ..core.config import Subproject
from ..core.model import NormalizedRun
from ..django_runner import ENV_OUTPUT
from . import _support

_RUNNER_PATH = "winnowdelta.django_runner.JUnitRunner"


def _winnowdelta_src_dir() -> str:
    # .../<root>/winnowdelta/__init__.py -> .../<root>
    return str(Path(winnowdelta.__file__).resolve().parent.parent)


class DjangoAdapter:
    stack = "django"
    command_kind = "test"

    def _base_command(self, sub: Subproject, cwd: Path) -> list[str]:
        configured = sub.command("test")
        if configured is not None:
            return configured
        python = runner.venv_python(cwd) or sys.executable
        return [python, "manage.py", "test"]

    def collect(
        self,
        sub: Subproject,
        cwd: Path,
        timeout: float | None = None,
        selection: list[str] | None = None,
    ) -> NormalizedRun:
        base = self._base_command(sub, cwd)
        sel = list(selection) if selection else []
        argv = [*base, *sel, f"--testrunner={_RUNNER_PATH}"]

        existing = os.environ.get("PYTHONPATH", "")
        pythonpath = os.pathsep.join(filter(None, [_winnowdelta_src_dir(), existing]))

        return _support.collect_via_report(
            command="test",
            cwd=cwd,
            report_name="django.xml",
            build_argv=lambda _report: argv,
            parse_text=partial(junit.parse_junit_xml, command="test", base=cwd),
            timeout=timeout,
            env={"PYTHONPATH": pythonpath},
            report_env_var=ENV_OUTPUT,
        )


register(DjangoAdapter())
