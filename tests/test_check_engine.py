"""Phase 4: check/baseline engine flow (fake runner + real config + store)."""

from __future__ import annotations

import json

import pytest

from winnowdelta.core import config, engine, runner
from winnowdelta.core.baseline import BaselineStore
from winnowdelta.core.model import Status


def _project(tmp_path, tools: list[str]) -> None:
    body = (
        "[subproject.app]\n"
        'stack = "vitest"\n'
        f"tools = {json.dumps(tools)}\n"
    )
    (tmp_path / config.CONFIG_NAME).write_text(body, encoding="utf-8")


def _eslint_payload(messages: list[dict]) -> str:
    return json.dumps([{"filePath": "a.ts", "messages": messages}])


def _fake_eslint(monkeypatch, messages: list[dict]) -> None:
    payload = _eslint_payload(messages)

    def run(command, cwd, env=None, timeout=None):  # type: ignore[no-untyped-def]
        return runner.ExecResult(1 if messages else 0, payload, "", 0.01, False)

    monkeypatch.setattr(runner, "run", run)


_MSG = {"ruleId": "no-unused", "severity": 2, "message": "x unused", "line": 3, "column": 1}
_MSG2 = {"ruleId": "eqeqeq", "severity": 2, "message": "use ===", "line": 9, "column": 1}


def test_check_all_reports_everything(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _project(tmp_path, ["eslint"])
    _fake_eslint(monkeypatch, [_MSG, _MSG2])
    run = engine.run_check(tmp_path, use_baseline=False)
    assert run.status is Status.FAILED
    assert len(run.diagnostics) == 2


def test_baseline_then_check_shows_only_new(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _project(tmp_path, ["eslint"])

    # Capture baseline with one pre-existing diagnostic.
    _fake_eslint(monkeypatch, [_MSG])
    cap = engine.capture_baseline(tmp_path)
    assert cap.status is Status.OK
    assert BaselineStore(tmp_path).exists("app")

    # Same diagnostic present -> nothing new.
    clean = engine.run_check(tmp_path)
    assert clean.status is Status.OK
    assert clean.diagnostics == []

    # A second diagnostic appears -> only that one is reported.
    _fake_eslint(monkeypatch, [_MSG, _MSG2])
    delta = engine.run_check(tmp_path)
    assert delta.status is Status.FAILED
    assert len(delta.diagnostics) == 1
    assert delta.diagnostics[0].rule == "eqeqeq"


def test_kind_filter_skips_other_tools(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # eslint is "lint"; asking for build runs nothing -> OK, no diagnostics.
    _project(tmp_path, ["eslint"])
    _fake_eslint(monkeypatch, [_MSG])
    run = engine.run_check(tmp_path, kind="build", use_baseline=False)
    assert run.status is Status.OK
    assert run.diagnostics == []


def test_tool_error_surfaces(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _project(tmp_path, ["eslint"])

    def run(command, cwd, env=None, timeout=None):  # type: ignore[no-untyped-def]
        return runner.ExecResult(2, "not json", "config blew up", 0.01, False)

    monkeypatch.setattr(runner, "run", run)
    result = engine.run_check(tmp_path, use_baseline=False)
    assert result.status is Status.ERROR
    assert "eslint" in (result.error or "")


def test_clear_baseline(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _project(tmp_path, ["eslint"])
    _fake_eslint(monkeypatch, [_MSG])
    engine.capture_baseline(tmp_path)
    assert engine.clear_baseline(tmp_path) is True
    assert engine.clear_baseline(tmp_path) is False
