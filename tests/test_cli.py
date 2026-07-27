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


def test_unhandled_error_exits_2_with_an_envelope(tmp_path, capsys) -> None:
    """An unreadable --tests-from file used to traceback out with exit 1.

    The documented contract is 0 clean / 1 failures / 2 tool error, so any
    escape has to be converted, not propagated.
    """
    missing = tmp_path / "nope.txt"
    code = cli.main(["test", "--tests-from", str(missing)])
    assert code == 2

    envelope = json.loads(capsys.readouterr().out)
    assert envelope["status"] == "error"
    assert "FileNotFoundError" in envelope["error"]


def test_unhandled_error_respects_text_mode(tmp_path, capsys) -> None:
    code = cli.main(["test", "--text", "--tests-from", str(tmp_path / "nope.txt")])
    assert code == 2
    assert capsys.readouterr().out.startswith("ERROR (test):")


def test_keyboard_interrupt_still_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ctrl-C must not be swallowed into an 'error' envelope."""
    monkeypatch.setattr(cli, "_cmd_test", _raise_interrupt)
    with pytest.raises(KeyboardInterrupt):
        cli.main(["test"])


def _raise_interrupt(args):  # type: ignore[no-untyped-def]
    raise KeyboardInterrupt


def test_baseline_clear_reports_config_error_as_exit_2(tmp_path, capsys, monkeypatch) -> None:
    """"no baseline to clear" + exit 0 used to mask an unresolvable config."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "winnowdelta.toml").write_text(
        '[subproject.a]\nstack = "pytest"\n[subproject.b]\nstack = "pytest"\n', encoding="utf-8"
    )
    code = cli.main(["baseline", "clear"])
    assert code == 2
    out = capsys.readouterr().out
    assert "ERROR" in out and "no baseline to clear" not in out
