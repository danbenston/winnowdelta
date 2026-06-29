"""Phase 4: diagnostic adapters via a fake runner (no node needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from winnowdelta.adapters.eslint_adapter import EslintAdapter
from winnowdelta.adapters.prettier_adapter import PrettierAdapter
from winnowdelta.adapters.tsc_adapter import TscAdapter
from winnowdelta.core import runner
from winnowdelta.core.config import Subproject
from winnowdelta.core.model import Status


def _fake(monkeypatch, *, stdout="", stderr="", exit_code=0, timed_out=False):
    def run(command, cwd, env=None, timeout=None):  # type: ignore[no-untyped-def]
        return runner.ExecResult(exit_code, stdout, stderr, 0.01, timed_out)

    monkeypatch.setattr(runner, "run", run)


SUB = Subproject("fe", "vitest")


def test_tsc_reports_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(
        monkeypatch,
        stdout="src/a.ts(1,2): error TS2322: bad type\n",
        exit_code=2,
    )
    run = TscAdapter().collect(SUB, Path("."))
    assert run.status is Status.FAILED
    assert run.diagnostics[0].rule == "TS2322"


def test_tsc_clean_is_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, stdout="", exit_code=0)
    assert TscAdapter().collect(SUB, Path(".")).status is Status.OK


def test_tsc_failure_without_diagnostics_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, stderr="error TS5058: cannot find tsconfig", exit_code=1)
    run = TscAdapter().collect(SUB, Path("."))
    assert run.status is Status.ERROR


def test_eslint_reports_and_handles_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        [{"filePath": "a.ts", "messages": [
            {"ruleId": "x", "severity": 2, "message": "m", "line": 1, "column": 1}]}]
    )
    _fake(monkeypatch, stdout=payload, exit_code=1)
    run = EslintAdapter().collect(SUB, Path("."))
    assert run.status is Status.FAILED and len(run.diagnostics) == 1

    _fake(monkeypatch, stdout="oops not json", stderr="config error", exit_code=2)
    assert EslintAdapter().collect(SUB, Path(".")).status is Status.ERROR


def test_prettier_diff_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, stdout="src/a.ts\nsrc/b.ts\n", exit_code=1)
    run = PrettierAdapter().collect(SUB, Path("."))
    assert run.status is Status.FAILED and len(run.diagnostics) == 2

    _fake(monkeypatch, stdout="", exit_code=0)
    assert PrettierAdapter().collect(SUB, Path(".")).status is Status.OK

    _fake(monkeypatch, stderr="boom", exit_code=2)
    assert PrettierAdapter().collect(SUB, Path(".")).status is Status.ERROR


def test_diag_timeout_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, timed_out=True, exit_code=1)
    run = TscAdapter().collect(SUB, Path("."), timeout=1.0)
    assert run.status is Status.ERROR and "timed out" in (run.error or "")
