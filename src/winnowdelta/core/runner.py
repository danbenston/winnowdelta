"""Process execution layer.

The one place that knows about the environment's sharp edges, so no adapter has
to re-solve them:

- **Windows node shims** — ``npm``/``npx``/``yarn``/``pnpm`` are ``.cmd`` files,
  not real executables; a bare name fails under ``subprocess``. We route them
  through ``ComSpec`` (``cmd.exe /c npm.cmd ...``).
- **Project venv** — resolve ``.venv``'s python so test invocations use the
  project's interpreter, not whatever is on PATH.
- **Per-subproject cwd** — every call takes an explicit working directory; we
  never assume a single repo root (oracle-rex runs Django at root and JS under
  ``frontend/``).
- **Timeouts + process-tree kill** — a hung suite is killed along with its
  children, not left orphaned.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

#: Node CLIs that are ``.cmd`` shims on Windows and need ComSpec routing.
NODE_TOOLS = frozenset({"npm", "npx", "yarn", "pnpm"})

_IS_WINDOWS = os.name == "nt"


@dataclass(frozen=True)
class ExecResult:
    """Raw result of running a command — no parsing yet."""

    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def build_argv(command: Sequence[str]) -> list[str]:
    """Translate a logical command into the actual argv to spawn.

    Pure and side-effect free so it can be unit-tested without spawning
    anything. On Windows, node tools are rewritten to ``cmd.exe /c <tool>.cmd``.
    """
    cmd = list(command)
    if not cmd:
        raise ValueError("empty command")
    if _IS_WINDOWS and cmd[0] in NODE_TOOLS:
        comspec = os.environ.get("ComSpec", "cmd.exe")
        return [comspec, "/c", cmd[0] + ".cmd", *cmd[1:]]
    return cmd


def resolve_executable(argv: list[str], cwd: str | os.PathLike[str]) -> list[str]:
    """Make a relative *path-like* executable absolute against *cwd*.

    Windows resolves a relative executable against the parent process's cwd, not
    the child's — so a configured command like ``.venv/Scripts/python.exe`` with
    a per-subproject ``cwd`` would not be found. If argv[0] looks like a path
    (contains a separator), is relative, and exists under *cwd*, rewrite it to an
    absolute path. Bare names (``npm``, ``python``) are left for PATH lookup.
    """
    if not argv:
        return argv
    prog = argv[0]
    looks_like_path = "/" in prog or "\\" in prog
    if looks_like_path and not os.path.isabs(prog):
        candidate = Path(cwd) / prog
        if candidate.exists():
            return [str(candidate.resolve()), *argv[1:]]
    return argv


def venv_python(root: str | os.PathLike[str]) -> str | None:
    """Return the project venv's python interpreter if one exists under *root*."""
    base = Path(root)
    candidate = (
        base / ".venv" / "Scripts" / "python.exe"
        if _IS_WINDOWS
        else base / ".venv" / "bin" / "python"
    )
    return str(candidate) if candidate.exists() else None


def _kill_tree(proc: subprocess.Popen[str]) -> None:
    """Kill *proc* and any children it spawned."""
    if _IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
        return
    # POSIX: kill the whole process group (these symbols are POSIX-only, so
    # access them via getattr to keep type-checking clean on Windows).
    killpg = getattr(os, "killpg", None)
    getpgid = getattr(os, "getpgid", None)
    sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
    if killpg is not None and getpgid is not None:
        try:
            killpg(getpgid(proc.pid), sigkill)
            return
        except (ProcessLookupError, PermissionError):
            pass
    proc.kill()


def run(
    command: Sequence[str],
    cwd: str | os.PathLike[str],
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> ExecResult:
    """Run *command* in *cwd* and capture its output.

    *env* is merged over the current environment (not replaced). On timeout the
    whole process tree is killed and ``timed_out`` is set.
    """
    argv = resolve_executable(build_argv(command), cwd)
    run_env = dict(os.environ)
    if env:
        run_env.update(env)

    start = time.monotonic()
    try:
        proc: subprocess.Popen[str] = subprocess.Popen(
            argv,
            cwd=os.fspath(cwd),
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            # POSIX: own process group so we can kill the whole tree. Ignored on nt.
            start_new_session=not _IS_WINDOWS,
        )
    except (FileNotFoundError, NotADirectoryError, OSError) as exc:
        # Missing toolchain / bad cwd: surface as a 127 result, not an exception,
        # so adapters report a clean ERROR rather than crashing.
        return ExecResult(
            exit_code=127,
            stdout="",
            stderr=f"failed to launch {argv[0]!r}: {exc}",
            duration_s=time.monotonic() - start,
        )

    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        stdout, stderr = proc.communicate()

    duration = time.monotonic() - start
    return ExecResult(
        exit_code=proc.returncode,
        stdout=stdout or "",
        stderr=stderr or "",
        duration_s=duration,
        timed_out=timed_out,
    )
