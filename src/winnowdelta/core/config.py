"""Configuration: ``winnowdelta.toml`` subproject definitions + autodetection.

The config exists primarily for multi-root monorepos (oracle-rex: Django at the
root, Vite/React under ``frontend/``). Each subproject pins a ``stack``, a
``cwd`` relative to the repo root, and the commands to run. When no config file
is present, a single subproject is synthesized by sniffing the repo.

Commands may be given as a TOML string or a list:

    [subproject.frontend]
    stack = "vitest"
    cwd   = "frontend"
    test  = "npm run test"            # string form (shlex-split, quotes kept)
    build = ["tsc", "-b"]             # list form (preferred for odd paths)

For Windows paths in string form, prefer forward slashes or the list form;
backslashes are preserved but spaces in unquoted paths are not.
"""

from __future__ import annotations

import shlex
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = "winnowdelta.toml"

#: Command kinds a subproject may define.
COMMAND_KINDS = ("test", "lint", "build")

#: Per-tool command overrides. A *kind* key is ambiguous whenever more than one
#: tool shares that kind — ``eslint`` and ``prettier`` are both ``lint``, so a
#: bare ``lint`` applies to both and cannot express "only change eslint's
#: command". These names let a single tool be overridden precisely; they take
#: precedence over the kind key.
TOOL_COMMANDS = ("tsc", "eslint", "prettier")

#: Every key accepted inside a ``[subproject.*]`` table. Anything else is a
#: typo, and silently ignoring it strands the user with a subproject that does
#: not do what its config says (``tool = [...]`` instead of ``tools = [...]``
#: yields "no tools ran" with no hint why).
_KNOWN_KEYS = frozenset({"stack", "cwd", "tools", *COMMAND_KINDS, *TOOL_COMMANDS})


class ConfigError(Exception):
    """Raised when ``winnowdelta.toml`` is malformed."""


@dataclass(frozen=True)
class Subproject:
    name: str
    stack: str
    cwd: str = "."
    commands: Mapping[str, list[str]] = field(default_factory=dict)
    #: Explicit diagnostic tools (e.g. ["eslint", "prettier", "tsc"]). Empty =>
    #: autodetect from the subproject's files.
    tools: tuple[str, ...] = ()

    def command(self, kind: str, *, tool: str | None = None) -> list[str] | None:
        """The configured argv for *kind*, or for *tool* specifically if set.

        A per-tool override wins over the kind it belongs to, so a subproject
        running both eslint and prettier can redirect one without touching the
        other. Falls back to the kind key, which applies to every tool of that
        kind.
        """
        for key in (tool, kind):
            if key is not None:
                argv = self.commands.get(key)
                if argv is not None:
                    return list(argv)
        return None

    def resolve_cwd(self, root: str | Path) -> Path:
        return (Path(root) / self.cwd).resolve()


@dataclass(frozen=True)
class Config:
    root: str
    subprojects: Mapping[str, Subproject]

    def get(self, name: str | None) -> Subproject:
        """Return a subproject by name, or the sole one when *name* is None."""
        if name is not None:
            if name not in self.subprojects:
                raise ConfigError(
                    f"unknown subproject {name!r}; known: {sorted(self.subprojects)}"
                )
            return self.subprojects[name]
        if len(self.subprojects) == 1:
            return next(iter(self.subprojects.values()))
        raise ConfigError(
            "multiple subprojects configured; specify one of "
            f"{sorted(self.subprojects)}"
        )


def _as_argv(value: object, where: str) -> list[str]:
    if isinstance(value, str):
        return shlex.split(value, posix=False)
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ConfigError(f"{where}: command must be a string or list, got {type(value).__name__}")


def load(root: str | Path) -> Config | None:
    """Load ``winnowdelta.toml`` from *root*, or return None if absent."""
    path = Path(root) / CONFIG_NAME
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc

    raw_subs = data.get("subproject")
    if not isinstance(raw_subs, dict):
        raise ConfigError(f"{path}: expected a [subproject.*] table")

    subprojects: dict[str, Subproject] = {}
    for name, spec in raw_subs.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"{path}: [subproject.{name}] must be a table")

        # Reject typos loudly. A silently-dropped key produces a subproject that
        # does not match its config and an empty result with no explanation.
        unknown = sorted(set(spec) - _KNOWN_KEYS)
        if unknown:
            raise ConfigError(
                f"{path}: subproject.{name} has unknown key(s) {unknown}; "
                f"known: {sorted(_KNOWN_KEYS)}"
            )

        stack = str(spec.get("stack", "")).strip()
        if not stack:
            raise ConfigError(f"{path}: subproject.{name} requires a non-empty 'stack'")

        commands: dict[str, list[str]] = {}
        for key in (*COMMAND_KINDS, *TOOL_COMMANDS):
            if key in spec:
                commands[key] = _as_argv(spec[key], f"subproject.{name}.{key}")

        raw_tools = spec.get("tools", [])
        if not isinstance(raw_tools, list):
            raise ConfigError(f"{path}: subproject.{name}.tools must be a list")
        subprojects[name] = Subproject(
            name=name,
            stack=stack,
            cwd=str(spec.get("cwd", ".")),
            commands=commands,
            tools=tuple(str(t) for t in raw_tools),
        )
    if not subprojects:
        raise ConfigError(f"{path}: no [subproject.*] tables defined")
    return Config(root=str(root), subprojects=subprojects)


def detect_stack(root: str | Path) -> str | None:
    """Best-effort framework sniff for the no-config fallback."""
    base = Path(root)
    if (base / "manage.py").exists():
        return "django"

    pkg = base / "package.json"
    if pkg.exists():
        text = pkg.read_text(encoding="utf-8", errors="replace")
        if "vitest" in text:
            return "vitest"
        if "jest" in text:
            return "jest"

    if (base / "pytest.ini").exists() or (base / "tox.ini").exists():
        return "pytest"
    pyproject = base / "pyproject.toml"
    if pyproject.exists():
        return "pytest"
    return None


_ESLINT_CONFIGS = (
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    "eslint.config.ts",
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.json",
    ".eslintrc.yml",
    ".eslintrc.yaml",
)
_PRETTIER_CONFIGS = (
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.js",
    ".prettierrc.cjs",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    "prettier.config.js",
    "prettier.config.cjs",
)


def detect_diagnostic_tools(cwd: str | Path) -> list[str]:
    """Sniff which build/lint tools apply to a subproject directory."""
    base = Path(cwd)
    tools: list[str] = []

    if any(base.glob("tsconfig*.json")):
        tools.append("tsc")
    if any((base / name).exists() for name in _ESLINT_CONFIGS):
        tools.append("eslint")

    has_prettier = any((base / name).exists() for name in _PRETTIER_CONFIGS)
    pkg = base / "package.json"
    if not has_prettier and pkg.exists():
        has_prettier = '"prettier"' in pkg.read_text(encoding="utf-8", errors="replace")
    if has_prettier:
        tools.append("prettier")

    return tools


def autodetect(root: str | Path) -> Config | None:
    """Synthesize a single-subproject config by sniffing *root*."""
    stack = detect_stack(root)
    if stack is None:
        return None
    sub = Subproject(name="default", stack=stack, cwd=".")
    return Config(root=str(root), subprojects={"default": sub})


def resolve(root: str | Path) -> Config | None:
    """Load config from disk, falling back to autodetection."""
    return load(root) or autodetect(root)
