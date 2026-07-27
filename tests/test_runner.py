"""Phase 1: execution layer."""

from __future__ import annotations

import sys
import time

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


def test_run_returns_when_process_exits_despite_lingering_grandchild(tmp_path) -> None:
    """Regression for the MCP-server Django hang.

    The child spawns a grandchild that inherits the child's stdout/stderr pipe
    handles and outlives it, then the child exits. On Windows ``communicate()``
    would block on the grandchild's copy of the write handle until it closed —
    the reported hang. ``run`` must return as soon as the *process* exits, well
    before the grandchild's (much longer) lifetime, and still capture the
    output the child flushed before exiting.
    """
    grandchild_sleep_s = 30
    grandchild = f"import time; time.sleep({grandchild_sleep_s})"
    script = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}]); "
        "print('child-done', flush=True)"
    )
    start = time.monotonic()
    result = runner.run([sys.executable, "-c", script], cwd=tmp_path, timeout=None)
    elapsed = time.monotonic() - start

    assert result.exit_code == 0
    assert result.timed_out is False
    assert "child-done" in result.stdout
    # Must not have waited out the grandchild. Generous ceiling for slow CI, but
    # still an order of magnitude below the grandchild's sleep.
    assert elapsed < grandchild_sleep_s / 2


def _res(stdout: str = "", stderr: str = "", exit_code: int = 1) -> runner.ExecResult:
    return runner.ExecResult(exit_code, stdout, stderr, 0.0, False)


def test_output_tail_prefers_stdout_over_npm_noise_on_stderr() -> None:
    """Regression: tsc reports on stdout, npx writes changelog notices to stderr.

    Picking stderr first produced errors like "npm notice To update run: ..."
    — the npm changelog instead of the reason the check failed.
    """
    noise = (
        "npm notice\n"
        "npm notice Changelog: https://github.com/npm/cli/releases/tag/v12.0.1\n"
        "npm notice To update run: npm install -g npm@12.0.1\n"
    )
    tail = runner.output_tail(_res(stdout="error TS5083: Cannot read tsconfig.json", stderr=noise))
    assert tail == "error TS5083: Cannot read tsconfig.json"


def test_output_tail_drops_npm_noise_even_when_stdout_is_empty() -> None:
    result = _res(stderr="npm warn exec\nnpm notice hi\nsh: tsc: not found\n")
    assert runner.output_tail(result) == "sh: tsc: not found"


def test_output_tail_keeps_npm_err_lines() -> None:
    """`npm ERR!` is the real cause, unlike `npm notice`/`npm warn`."""
    result = _res(stderr="npm notice x\nnpm ERR! could not determine executable to run\n")
    assert runner.output_tail(result) == "npm ERR! could not determine executable to run"


def test_output_tail_still_falls_back_to_stderr_and_exit_code() -> None:
    # Missing-toolchain path: run() puts its diagnosis on stderr with no stdout.
    assert "failed to launch" in runner.output_tail(_res(stderr="failed to launch 'nope': ..."))
    # Nothing meaningful anywhere: the exit code is all we have.
    assert runner.output_tail(_res(stderr="npm notice only\n", exit_code=9)) == "exited 9"


def test_output_tail_strips_ansi_colour_codes() -> None:
    """Colourized tool output must not leak escape codes into the JSON envelope."""
    result = _res(stderr="Use \x1b[1mnpm install typescript\x1b[0m first")
    assert runner.output_tail(result) == "Use npm install typescript first"
