"""Phase 3: adapter command construction + collect path, with a fake runner.

No node/Django needed — the fake runner captures argv/env and writes a canned
report to the path the adapter chose, so the whole collect() flow is exercised.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from winnowdelta import django_runner
from winnowdelta.adapters.django_adapter import DjangoAdapter
from winnowdelta.adapters.jest_adapter import JestAdapter
from winnowdelta.adapters.vitest_adapter import VitestAdapter
from winnowdelta.core import runner
from winnowdelta.core.config import Subproject
from winnowdelta.core.model import Status
from winnowdelta.django_runner import ENV_OUTPUT, CaseResult, build_junit_xml

_JEST_FAIL = json.dumps(
    {
        "testResults": [
            {
                "name": "a.test.ts",
                "assertionResults": [
                    {
                        "status": "failed",
                        "title": "t",
                        "failureMessages": ["Error: expected 1 to be 2\n ❯ a.test.ts:3:1\n"],
                    }
                ],
            }
        ]
    }
)


class _Fake:
    """Captures the last invocation and writes canned report content."""

    def __init__(self, content: str, *, exit_code: int, report_from_env: str | None = None):
        self.content = content
        self.exit_code = exit_code
        self.report_from_env = report_from_env
        self.argv: list[str] = []
        self.env: dict[str, str] | None = None

    def __call__(self, command, cwd, env=None, timeout=None):  # type: ignore[no-untyped-def]
        self.argv = list(command)
        self.env = dict(env) if env else None
        if self.report_from_env:
            path = (env or {})[self.report_from_env]
        else:
            i = command.index("--outputFile")
            path = command[i + 1]
        Path(path).write_text(self.content, encoding="utf-8")
        return runner.ExecResult(self.exit_code, "", "", 0.01, False)


def test_vitest_default_command_and_parse(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    fake = _Fake(_JEST_FAIL, exit_code=1)
    monkeypatch.setattr(runner, "run", fake)
    run = VitestAdapter().collect(Subproject("default", "vitest"), tmp_path)

    assert run.status is Status.FAILED
    assert fake.argv[:3] == ["npx", "vitest", "run"]
    assert "--reporter=json" in fake.argv


def test_vitest_honors_configured_command(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    fake = _Fake(_JEST_FAIL, exit_code=1)
    monkeypatch.setattr(runner, "run", fake)
    sub = Subproject("fe", "vitest", commands={"test": ["pnpm", "vitest", "run"]})
    VitestAdapter().collect(sub, tmp_path)
    assert fake.argv[:3] == ["pnpm", "vitest", "run"]


def test_jest_default_flags(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    fake = _Fake(_JEST_FAIL, exit_code=1)
    monkeypatch.setattr(runner, "run", fake)
    JestAdapter().collect(Subproject("m", "jest"), tmp_path)
    for flag in ("--ci", "--passWithNoTests", "--json"):
        assert flag in fake.argv
    assert fake.argv[:2] == ["npx", "jest"]


def test_django_injects_runner_and_pythonpath(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    xml = build_junit_xml(
        [
            CaseResult(
                test_id="app.tests.T::test_x",
                classname="app.tests.T",
                name="test_x",
                status="failed",
                file="app/tests.py",
                line=12,
                message="AssertionError: 1 != 2",
                text="Traceback ...",
            )
        ]
    )
    fake = _Fake(xml, exit_code=1, report_from_env=ENV_OUTPUT)
    monkeypatch.setattr(runner, "run", fake)

    run = DjangoAdapter().collect(Subproject("backend", "django"), tmp_path)

    assert run.status is Status.FAILED
    assert run.failures[0].file == "app/tests.py"
    assert run.failures[0].line == 12
    assert any(a.startswith("--testrunner=winnowdelta_django_runner") for a in fake.argv)
    assert fake.env is not None
    assert "winnowdelta" in fake.env["PYTHONPATH"].lower()
    assert ENV_OUTPUT in fake.env


def test_django_pythonpath_exposes_only_the_staged_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The dir put on the target's PYTHONPATH must hold nothing but the runner.

    Under a pip install winnowdelta's own parent dir is site-packages, and
    prepending that would shadow the target project's dependencies with
    winnowdelta's. Snapshot the directory *during* the call — it is a temp dir
    that no longer exists once collect() returns.
    """
    fake = _Fake(build_junit_xml([]), exit_code=0, report_from_env=ENV_OUTPUT)
    exposed: list[list[str]] = []

    def spy(command, cwd, env=None, timeout=None):  # type: ignore[no-untyped-def]
        first = Path((env or {})["PYTHONPATH"].split(os.pathsep)[0])
        exposed.append(sorted(p.name for p in first.iterdir()))
        return fake(command, cwd, env, timeout)

    monkeypatch.setattr(runner, "run", spy)
    DjangoAdapter().collect(Subproject("backend", "django"), tmp_path)

    assert exposed == [["winnowdelta_django_runner.py"]]


def test_django_staged_runner_is_importable_standalone(tmp_path) -> None:
    """The staged copy must import as a top-level module, with no winnowdelta package.

    It is loaded by the *target project's* interpreter, which has no winnowdelta
    installed — so any package-relative import in django_runner.py would break
    the whole Django path.
    """
    staged = tmp_path / "winnowdelta_django_runner.py"
    shutil.copyfile(django_runner.__file__, staged)
    proc = subprocess.run(
        [sys.executable, "-c", "import winnowdelta_django_runner as m; print(m.ENV_OUTPUT)"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path), "PYTHONSAFEPATH": "1"},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ENV_OUTPUT


def test_adapter_timeout_is_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    def timed_out(command, cwd, env=None, timeout=None):  # type: ignore[no-untyped-def]
        return runner.ExecResult(1, "", "", 0.01, True)

    monkeypatch.setattr(runner, "run", timed_out)
    run = VitestAdapter().collect(Subproject("fe", "vitest"), tmp_path, timeout=0.5)
    assert run.status is Status.ERROR
    assert "timed out" in (run.error or "")
