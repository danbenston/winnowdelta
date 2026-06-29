# Configuration — `winnowdelta.toml`

winnowdelta runs with **zero config** in a single-stack repo: it autodetects the
test runner (pytest / Vitest / Jest / Django) and the diagnostic tools (tsc /
ESLint / Prettier) by sniffing the directory. A `winnowdelta.toml` at the repo
root is needed only for multi-root monorepos or to override commands.

## Subprojects

Each `[subproject.<name>]` table declares one runnable unit:

| Key | Meaning | Default |
|---|---|---|
| `stack` | Test runner: `pytest` \| `django` \| `vitest` \| `jest` | — (required) |
| `cwd` | Working directory, relative to the repo root | `"."` |
| `test` / `lint` / `build` | Override the command for that kind (string or list) | autodetected |
| `tools` | Explicit diagnostic tools, e.g. `["eslint","prettier","tsc"]` | autodetected from `cwd` |

Commands are a TOML string (shlex-split, backslashes preserved) or a list
(preferred for paths with spaces):

```toml
test  = ".venv/Scripts/python.exe manage.py test"   # string
build = ["tsc", "-b"]                                # list
```

When a single subproject is configured (or autodetected), commands that take a
`subproject` argument may omit it.

## Multi-root example (oracle-rex)

A two-root monorepo: a Django backend at the root and a Vite/React frontend
under `frontend/`.

```toml
[subproject.backend]
stack = "django"
cwd   = "."
test  = ".venv/Scripts/python.exe manage.py test core"   # explicit app label, see below

[subproject.frontend]
stack = "vitest"
cwd   = "frontend"
tools = ["eslint", "prettier", "tsc"]
```

Run a specific subproject:

```sh
winnowdelta test backend
winnowdelta check frontend --kind lint
```

## Invocation quirks handled for you

- **Windows node shims** — `npm`/`npx`/`yarn`/`pnpm` are `.cmd` files; winnowdelta
  routes them through `ComSpec` (`cmd.exe /c npm.cmd …`) so they run on Windows.
- **Project venv** — when a subproject has a `.venv`, its Python is used for
  pytest/Django invocations.
- **Per-subproject cwd** — every command runs in its own `cwd`; no single-root
  assumption.

## Known quirk: Django test discovery

Django's `manage.py test` auto-discovery walks **up** from the start directory
while a package (`__init__.py`) is present. If your repo root has an
`__init__.py` *and* a non-identifier directory name (e.g. a hyphen, as in
`oracle-rex`), discovery builds an invalid module path and fails to import —
this happens with the stock runner too, not just winnowdelta. Work around it by
giving `test` an explicit app label (`manage.py test core`) or by configuring
discovery so it doesn't climb past the project root.
