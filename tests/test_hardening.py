"""Phase 7: hardening — missing toolchain and adapter-crash isolation."""

from __future__ import annotations

import json

import pytest

from winnowdelta.core import config, engine, runner
from winnowdelta.core.model import Status


def test_missing_executable_yields_127_not_exception(tmp_path) -> None:
    result = runner.run(["winnowdelta-no-such-binary-xyz"], cwd=tmp_path)
    assert result.exit_code == 127
    assert not result.ok
    assert "failed to launch" in result.stderr


def test_engine_reports_missing_test_tool_as_error(tmp_path) -> None:
    # A pytest subproject whose command points at a non-existent binary.
    (tmp_path / config.CONFIG_NAME).write_text(
        '[subproject.x]\nstack = "pytest"\ntest = ["no-such-binary-xyz"]\n',
        encoding="utf-8",
    )
    run = engine.run_test(tmp_path)
    assert run.status is Status.ERROR
    assert run.error is not None


def test_adapter_crash_is_isolated_to_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    (tmp_path / config.CONFIG_NAME).write_text(
        '[subproject.x]\nstack = "pytest"\n', encoding="utf-8"
    )

    def boom(*a, **k):  # type: ignore[no-untyped-def]
        raise RuntimeError("unexpected")

    adp = engine.registry.get("pytest")
    assert adp is not None
    monkeypatch.setattr(adp, "collect", boom)

    run = engine.run_test(tmp_path)
    assert run.status is Status.ERROR
    assert "adapter failed" in (run.error or "")


def test_diagnostic_tool_crash_is_isolated(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    (tmp_path / config.CONFIG_NAME).write_text(
        '[subproject.x]\nstack = "vitest"\ntools = ["eslint"]\n', encoding="utf-8"
    )

    def boom(*a, **k):  # type: ignore[no-untyped-def]
        raise RuntimeError("eslint exploded")

    adp = engine.registry.get_diagnostic("eslint")
    assert adp is not None
    monkeypatch.setattr(adp, "collect", boom)

    run = engine.run_check(tmp_path, use_baseline=False)
    assert run.status is Status.ERROR
    assert "eslint" in (run.error or "")


def test_schema_version_is_frozen_v1() -> None:
    from winnowdelta.core.model import NormalizedRun
    from winnowdelta.core.output import SCHEMA_VERSION, to_envelope

    assert SCHEMA_VERSION == "1.0"
    env = json.loads(json.dumps(to_envelope(NormalizedRun.empty("test"))))
    assert env["schema_version"] == "1.0"
