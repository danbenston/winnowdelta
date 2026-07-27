"""Django adapter (Feature #1) — the hard one.

``manage.py test`` has no native structured reporter, so we inject a JUnit
runner (which needs no extra package in the target venv) and read the JUnit XML
it writes via the shared ``core.junit`` parser. The target's interpreter has to
be able to import that runner, which means putting a directory on the
subprocess ``PYTHONPATH`` — and *which* directory matters: winnowdelta's own
parent dir is ``site-packages`` under a normal pip install, and prepending that
would put every package in winnowdelta's environment ahead of the target
project's own (a different Django would silently win). So we stage a copy of
``django_runner.py`` — deliberately stdlib-only — alone in a temp directory and
expose only that.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from .. import django_runner
from ..core import junit, runner
from ..core.adapter import register
from ..core.config import Subproject
from ..core.model import NormalizedRun
from ..django_runner import ENV_OUTPUT
from . import _support

#: Top-level module name the staged copy is imported as inside the subprocess.
#: Deliberately not ``winnowdelta.django_runner`` — the staged file stands alone
#: and is not part of a package.
_STAGED_MODULE = "winnowdelta_django_runner"


@contextmanager
def _runner_on_path() -> Iterator[tuple[str, str]]:
    """Yield ``(dir_for_PYTHONPATH, dotted_runner_path)``.

    Normally that is a temp dir holding nothing but a copy of
    ``django_runner.py``. If the copy can't be made — winnowdelta imported from
    a zipimport/egg, where ``__file__`` is not a real file — fall back to
    exposing winnowdelta's parent dir and importing the runner in place, which
    is the older, path-polluting behavior but better than failing outright.
    """
    source = Path(django_runner.__file__)
    tmpdir = Path(tempfile.mkdtemp(prefix="winnowdelta-runner-"))
    try:
        shutil.copyfile(source, tmpdir / f"{_STAGED_MODULE}.py")
    except OSError:
        shutil.rmtree(tmpdir, ignore_errors=True)
        # .../<root>/winnowdelta/django_runner.py -> .../<root>
        yield str(source.resolve().parent.parent), "winnowdelta.django_runner.JUnitRunner"
        return
    try:
        yield str(tmpdir), f"{_STAGED_MODULE}.JUnitRunner"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


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

        with _runner_on_path() as (runner_dir, runner_path):
            argv = [*base, *sel, f"--testrunner={runner_path}"]
            existing = os.environ.get("PYTHONPATH", "")
            pythonpath = os.pathsep.join(filter(None, [runner_dir, existing]))

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
