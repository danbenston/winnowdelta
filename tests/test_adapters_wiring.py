"""Phase 3: adapter command construction + collect path, with a fake runner.

No node/Django needed — the fake runner captures argv/env and writes a canned
report to the path the adapter chose, so the whole collect() flow is exercised.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    assert any(a.startswith("--testrunner=winnowdelta.django_runner") for a in fake.argv)
    assert fake.env is not None
    assert "winnowdelta" in fake.env["PYTHONPATH"].lower()
    assert ENV_OUTPUT in fake.env


def test_adapter_timeout_is_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    def timed_out(command, cwd, env=None, timeout=None):  # type: ignore[no-untyped-def]
        return runner.ExecResult(1, "", "", 0.01, True)

    monkeypatch.setattr(runner, "run", timed_out)
    run = VitestAdapter().collect(Subproject("fe", "vitest"), tmp_path, timeout=0.5)
    assert run.status is Status.ERROR
    assert "timed out" in (run.error or "")
