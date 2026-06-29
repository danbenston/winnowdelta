"""Phase 0 smoke tests: the package imports, the CLI runs, the envelope is valid."""

from __future__ import annotations

import json

import pytest

from winnowdelta import __version__, cli
from winnowdelta.cli import SCHEMA_VERSION, build_parser, main
from winnowdelta.core.model import Failure, NormalizedRun, Status, Summary


def test_version_string() -> None:
    assert __version__


def test_help_runs(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "winnowdelta" in out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_test_command_emits_valid_envelope(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli.engine, "run_test", lambda *a, **k: NormalizedRun.empty("test"))
    assert main(["test"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["command"] == "test"
    assert payload["status"] == "ok"
    assert payload["failures"] == []
    assert payload["diagnostics"] == []


def test_exit_code_reflects_status(monkeypatch: pytest.MonkeyPatch) -> None:
    failed = NormalizedRun(
        command="test",
        status=Status.FAILED,
        failures=[Failure(test_id="t::a")],
        summary=Summary(total=1, failed=1),
    )
    monkeypatch.setattr(cli.engine, "run_test", lambda *a, **k: failed)
    assert main(["test"]) == 1

    monkeypatch.setattr(
        cli.engine, "run_test", lambda *a, **k: NormalizedRun.errored("test", "boom")
    )
    assert main(["test"]) == 2


def test_parser_builds() -> None:
    assert build_parser().prog == "winnowdelta"
