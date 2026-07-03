# Known issues

## 1. MCP `test` hangs on a Django subproject while the CLI succeeds (Windows)

**Status:** **fixed** 2026-07-03 in `core/runner.py`. **Severity:** high (the MCP
surface was unusable for Django on this setup). **Found:** 2026-07-03, against the
`oracle-rex` project on Windows.

### Fix

`core.runner.run` no longer completes via `proc.communicate()`, which on Windows
blocks until *every* copy of the child's stdout/stderr write handle is closed —
including one a lingering grandchild inherited. It now:

1. spawns the child with `stdin=subprocess.DEVNULL` so no child ever reads the
   server's JSON-RPC stdin;
2. drains stdout/stderr on background daemon threads and keys completion off the
   child **process** exiting (`proc.wait`), not off pipe EOF; and
3. after the process exits, joins the drain threads under a shared
   `_DRAIN_GRACE_S` (2s) ceiling — so a grandchild still holding the pipe open
   yields "return with what we captured" instead of an indefinite hang.

Regression: `tests/test_runner.py::test_run_returns_when_process_exits_despite_lingering_grandchild`
spawns a child that leaves a long-lived grandchild holding the pipe handles and
asserts `run` returns promptly after the child exits. The original analysis
follows.

### Symptom

`run_tests` via the **MCP server** (`winnowdelta.mcp.server`) hangs indefinitely
on a Django subproject and eventually returns
`{"status":"error","error":"test timed out after <N>s"}` (or, with no timeout,
runs for minutes producing no output). The **CLI** runs the *identical* config,
command, core runner, and adapter and succeeds in ~9s:

```jsonc
// winnowdelta test backend   (CLI — WORKS)
{"schema_version":"1.0","command":"test","status":"ok",
 "summary":{"total":145,"passed":145,"failed":0,"skipped":0},"duration_s":9.356}

// mcp run_tests(subproject="backend")  (MCP — HANGS -> timeout error)
{"schema_version":"1.0","command":"test","status":"error",
 "summary":{"total":0,...},"error":"test timed out after 150.0s"}
```

### What was ruled out

The bug is **not** in the config, the Django adapter, the core runner, or the
target command. All of these were verified good:

- The exact spawned argv
  `.venv/Scripts/python.exe manage.py test core.tests --testrunner=winnowdelta.django_runner.JUnitRunner`
  with `PYTHONPATH=<winnowdelta>/src` and `WINNOWDELTA_JUNIT=<tmp>` completes in
  ~7s and writes a valid 31 KB JUnit report when spawned directly from a shell.
- Verified with `stdin` = `/dev/null` **and** `stdin` = an open pipe that never
  sends EOF (`sleep 45 | …`, mimicking an inherited MCP stdin) — **both finish in
  ~7s.** So a plain inherited/blocking stdin is *not* sufficient to reproduce.
- `winnowdelta test backend` from the **CLI** (same `core.runner.run`, same
  `DjangoAdapter`, same `winnowdelta.toml`) → 145/145 pass, ~9s.

The single differing variable is the **invocation surface**: the hang appears
only when the child is spawned by the long-lived stdio **MCP server** process.

### Likely cause + suggested investigation

The MCP server is launched by the host as a stdio process
(`python -m winnowdelta.mcp.server`, no explicit `cwd`), so its `stdin`/`stdout`
are the JSON-RPC pipes to the host. `core.runner.run` spawns the child with
`stdout=PIPE, stderr=PIPE` but **does not set `stdin`** and does not force
Windows handle-inheritance off, so:

- the child (and any grandchild process/thread the Django suite starts) can
  inherit the server's JSON-RPC pipe handles, and on Windows `communicate()`
  blocks until *every* copy of the child's stdout/stderr write handle is closed —
  a lingering grandchild that inherited a handle keeps it open forever.

Things to try in `core/runner.py` / the MCP server:

1. `subprocess.Popen(..., stdin=subprocess.DEVNULL)` — never let a child read the
   server's JSON-RPC stdin.
2. Ensure the child does not inherit the server's stdio handles: on Windows,
   spawn with `close_fds=True` semantics for the redirected handles and/or
   `creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS`, or reopen the server's
   own stdio as non-inheritable at startup.
3. Distinguish "process exited" from "pipe EOF": read pipes on threads and stop
   waiting once `proc.wait()` returns, rather than blocking on `communicate()`
   for handle closure.

A regression test should exercise the **MCP tool** end-to-end against a real
subprocess that leaves a short-lived grandchild alive, on Windows — the existing
`test_django_runner.py` only unit-tests the XML builder and never spawns through
the MCP server, which is why this slipped through.

### Workaround (for consumers, e.g. oracle-rex)

Use the **CLI** (`winnowdelta test backend`) or the project's raw runner
(`.venv/Scripts/python.exe manage.py test core.tests`) until the MCP hang is
fixed. Do not rely on the MCP `run_tests` tool for Django subprojects on Windows.

## 2. Django adapter default can't run a hyphenated-root repo

**Status:** documented; mitigated by config. See
[configuration.md](configuration.md#known-quirk-django-test-discovery).

The Django adapter's zero-config default is bare `manage.py test`, which fails
Django auto-discovery when the repo root has an `__init__.py` and a
non-identifier name (`oracle-rex`). Even the app label `manage.py test core`
fails; only the package label `manage.py test core.tests` works. So for such
repos an explicit `test` in `winnowdelta.toml` is **required**, and the docs'
example was corrected (`core` → `core.tests`). Consider having the adapter detect
this discovery failure and surface a clear, fast error pointing at the config
fix, instead of relying on the default.
