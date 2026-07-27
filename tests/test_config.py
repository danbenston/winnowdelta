"""Phase 1: config loading + autodetection."""

from __future__ import annotations

import pytest

from winnowdelta.core import config


def _write(tmp_path, body: str):
    (tmp_path / config.CONFIG_NAME).write_text(body, encoding="utf-8")
    return tmp_path


def test_load_absent_returns_none(tmp_path) -> None:
    assert config.load(tmp_path) is None


def test_load_multiroot(tmp_path) -> None:
    _write(
        tmp_path,
        """
[subproject.backend]
stack = "django"
test = ".venv/Scripts/python.exe manage.py test"

[subproject.frontend]
stack = "vitest"
cwd = "frontend"
test = "npm run test"
build = ["tsc", "-b"]
""",
    )
    cfg = config.load(tmp_path)
    assert cfg is not None
    assert set(cfg.subprojects) == {"backend", "frontend"}

    backend = cfg.get("backend")
    assert backend.stack == "django"
    assert backend.command("test") == [".venv/Scripts/python.exe", "manage.py", "test"]

    frontend = cfg.get("frontend")
    assert frontend.cwd == "frontend"
    assert frontend.command("test") == ["npm", "run", "test"]
    assert frontend.command("build") == ["tsc", "-b"]
    assert frontend.command("lint") is None


def test_get_ambiguous_without_name(tmp_path) -> None:
    _write(
        tmp_path,
        """
[subproject.a]
stack = "pytest"
[subproject.b]
stack = "pytest"
""",
    )
    cfg = config.load(tmp_path)
    assert cfg is not None
    with pytest.raises(config.ConfigError):
        cfg.get(None)


def test_get_unknown_name(tmp_path) -> None:
    _write(tmp_path, '[subproject.a]\nstack = "pytest"\n')
    cfg = config.load(tmp_path)
    assert cfg is not None
    with pytest.raises(config.ConfigError):
        cfg.get("nope")


def test_resolve_cwd(tmp_path) -> None:
    _write(tmp_path, '[subproject.fe]\nstack = "vitest"\ncwd = "frontend"\n')
    cfg = config.load(tmp_path)
    assert cfg is not None
    resolved = cfg.get("fe").resolve_cwd(tmp_path)
    assert resolved == (tmp_path / "frontend").resolve()


def test_malformed_subproject_table(tmp_path) -> None:
    _write(tmp_path, "subproject = 5\n")
    with pytest.raises(config.ConfigError):
        config.load(tmp_path)


def test_detect_stack_django(tmp_path) -> None:
    (tmp_path / "manage.py").write_text("")
    assert config.detect_stack(tmp_path) == "django"


def test_detect_stack_vitest_and_jest(tmp_path) -> None:
    (tmp_path / "package.json").write_text('{"devDependencies": {"vitest": "^1"}}')
    assert config.detect_stack(tmp_path) == "vitest"
    (tmp_path / "package.json").write_text('{"devDependencies": {"jest": "^29"}}')
    assert config.detect_stack(tmp_path) == "jest"


def test_detect_stack_pytest_from_pyproject(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert config.detect_stack(tmp_path) == "pytest"


def test_autodetect_synthesizes_single_subproject(tmp_path) -> None:
    (tmp_path / "manage.py").write_text("")
    cfg = config.autodetect(tmp_path)
    assert cfg is not None
    assert cfg.get(None).stack == "django"


def test_resolve_prefers_config_over_detection(tmp_path) -> None:
    (tmp_path / "manage.py").write_text("")
    _write(tmp_path, '[subproject.x]\nstack = "pytest"\n')
    cfg = config.resolve(tmp_path)
    assert cfg is not None
    assert set(cfg.subprojects) == {"x"}


def test_unknown_subproject_key_is_rejected(tmp_path) -> None:
    """Typos used to be dropped silently, leaving a subproject that ignores its config.

    `tool = [...]` instead of `tools = [...]` yielded "no tools ran" with no hint.
    """
    _write(tmp_path, '[subproject.x]\nstack = "vitest"\ntool = ["eslint"]\n')
    with pytest.raises(config.ConfigError, match="unknown key"):
        config.load(tmp_path)


def test_missing_or_empty_stack_is_rejected(tmp_path) -> None:
    _write(tmp_path, '[subproject.x]\ncwd = "frontend"\n')
    with pytest.raises(config.ConfigError, match="stack"):
        config.load(tmp_path)
    _write(tmp_path, '[subproject.x]\nstack = "  "\n')
    with pytest.raises(config.ConfigError, match="stack"):
        config.load(tmp_path)


def test_per_tool_command_beats_the_kind_command(tmp_path) -> None:
    """A kind key alone cannot express "only change eslint" — both lint tools share it."""
    _write(
        tmp_path,
        '[subproject.x]\nstack = "vitest"\n'
        'lint = ["npx", "shared"]\n'
        'eslint = ["npx", "eslint", "--format", "json"]\n',
    )
    sub = config.load(tmp_path).get("x")
    assert sub.command("lint", tool="eslint") == ["npx", "eslint", "--format", "json"]
    # prettier has no per-tool key, so it falls back to the shared kind command.
    assert sub.command("lint", tool="prettier") == ["npx", "shared"]
    assert sub.command("lint") == ["npx", "shared"]


def test_command_returns_none_when_neither_key_is_set(tmp_path) -> None:
    _write(tmp_path, '[subproject.x]\nstack = "vitest"\n')
    sub = config.load(tmp_path).get("x")
    assert sub.command("lint", tool="eslint") is None
