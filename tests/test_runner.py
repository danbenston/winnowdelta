"""Phase 1: execution layer."""

from __future__ import annotations

import sys

import pytest

from winnowdelta.core import runner


def test_build_argv_passthrough_non_node() -> None:
    assert runner.build_argv(["python", "-c", "pass"]) == ["python", "-c", "pass"]


def test_build_argv_empty_raises() -> None:
    with pytest.raises(ValueError):
        runner.build_argv([])


def test_build_argv_node_tool_uses_comspec_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "_IS_WINDOWS", True)
    monkeypatch.setenv("ComSpec", r"C:\Windows\System32\cmd.exe")
    argv = runner.build_argv(["npm", "run", "test"])
    assert argv == [r"C:\Windows\System32\cmd.exe", "/c", "npm.cmd", "run", "test"]


def test_build_argv_node_tool_passthrough_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "_IS_WINDOWS", False)
    assert runner.build_argv(["npm", "run", "test"]) == ["npm", "run", "test"]


def test_venv_python_detected(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "_IS_WINDOWS", False)
    bin_dir = tmp_path / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").write_text("")
    assert runner.venv_python(tmp_path) == str(bin_dir / "python")


def test_venv_python_absent(tmp_path) -> None:
    assert runner.venv_python(tmp_path) is None


def test_resolve_executable_makes_relative_path_absolute(tmp_path) -> None:
    sub = tmp_path / ".venv" / "Scripts"
    sub.mkdir(parents=True)
    exe = sub / "python.exe"
    exe.write_text("")
    out = runner.resolve_executable([".venv/Scripts/python.exe", "x"], tmp_path)
    assert out[0] == str(exe.resolve())
    assert out[1] == "x"


def test_resolve_executable_leaves_bare_names(tmp_path) -> None:
    # No separator -> PATH lookup, untouched.
    assert runner.resolve_executable(["python", "-c", "pass"], tmp_path) == [
        "python", "-c", "pass",
    ]


def test_resolve_executable_leaves_missing_relative_path(tmp_path) -> None:
    argv = ["./nope/python.exe"]
    assert runner.resolve_executable(argv, tmp_path) == argv


def test_run_captures_stdout_and_exit_code(tmp_path) -> None:
    result = runner.run([sys.executable, "-c", "print('hi')"], cwd=tmp_path)
    assert result.ok
    assert result.exit_code == 0
    assert "hi" in result.stdout
    assert result.timed_out is False


def test_run_nonzero_exit(tmp_path) -> None:
    result = runner.run([sys.executable, "-c", "import sys; sys.exit(3)"], cwd=tmp_path)
    assert result.exit_code == 3
    assert not result.ok


def test_run_timeout_kills(tmp_path) -> None:
    result = runner.run(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=tmp_path,
        timeout=0.5,
    )
    assert result.timed_out is True
    assert not result.ok
