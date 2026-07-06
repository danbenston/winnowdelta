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


def _capture_argv(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Record the argv the adapter hands to the runner (clean-exit stub)."""
    seen: dict[str, list[str]] = {}

    def run(command, cwd, env=None, timeout=None):  # type: ignore[no-untyped-def]
        seen["argv"] = command
        return runner.ExecResult(0, "", "", 0.01, False)

    monkeypatch.setattr(runner, "run", run)
    return seen


def test_tsc_uses_build_mode_for_project_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Solution-style root: plain `tsc --noEmit` would type-check nothing here.
    (tmp_path / "tsconfig.json").write_text(
        '{\n  "files": [],\n  "references": [{ "path": "./contracts" }]\n}',
        encoding="utf-8",
    )
    seen = _capture_argv(monkeypatch)
    TscAdapter().collect(SUB, tmp_path)
    assert "-b" in seen["argv"]
    assert "--noEmit" not in seen["argv"]


def test_tsc_uses_build_mode_for_composite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "tsconfig.json").write_text(
        '{ "compilerOptions": { "composite": true } }', encoding="utf-8"
    )
    seen = _capture_argv(monkeypatch)
    TscAdapter().collect(SUB, tmp_path)
    assert "-b" in seen["argv"]


def test_tsc_uses_plain_noemit_for_flat_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "tsconfig.json").write_text(
        '{ "compilerOptions": { "strict": true } }', encoding="utf-8"
    )
    seen = _capture_argv(monkeypatch)
    TscAdapter().collect(SUB, tmp_path)
    assert "--noEmit" in seen["argv"]
    assert "-b" not in seen["argv"]


def test_tsc_empty_references_is_flat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An empty references array is not a composite project; stay in flat mode.
    (tmp_path / "tsconfig.json").write_text('{ "references": [] }', encoding="utf-8")
    seen = _capture_argv(monkeypatch)
    TscAdapter().collect(SUB, tmp_path)
    assert "-b" not in seen["argv"]
    assert "--noEmit" in seen["argv"]


def test_tsc_missing_tsconfig_defaults_to_flat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _capture_argv(monkeypatch)
    TscAdapter().collect(SUB, tmp_path)
    assert "--noEmit" in seen["argv"]


def test_tsc_build_override_beats_detection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "tsconfig.json").write_text(
        '{ "references": [{ "path": "x" }] }', encoding="utf-8"
    )
    sub = Subproject("fe", "vitest", commands={"build": ["tsc", "--noEmit", "-p", "custom.json"]})
    seen = _capture_argv(monkeypatch)
    TscAdapter().collect(sub, tmp_path)
    assert seen["argv"] == ["tsc", "--noEmit", "-p", "custom.json"]


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
