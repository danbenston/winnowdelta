"""Phase 6: MCP tool functions (pure; no mcp SDK needed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from winnowdelta.core import engine
from winnowdelta.core.model import NormalizedRun
from winnowdelta.core.output import SCHEMA_VERSION
from winnowdelta.mcp import tools

BASIC = Path(__file__).parent / "fixtures" / "pytest_basic"


def test_run_tests_returns_envelope() -> None:
    env = tools.run_tests(root=str(BASIC))
    assert env["schema_version"] == SCHEMA_VERSION
    assert env["status"] == "failed"
    assert len(env["failures"]) == 2  # type: ignore[arg-type]


def test_run_tests_selection_narrows() -> None:
    env = tools.run_tests(root=str(BASIC), selection=["test_sample.py::test_passes"])
    assert env["status"] == "ok"
    assert env["summary"] == {"total": 1, "passed": 1, "failed": 0, "skipped": 0}


def test_run_tests_full_ignores_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake(root, subproject=None, timeout=None, selection=None):  # type: ignore[no-untyped-def]
        captured["selection"] = selection
        return NormalizedRun.empty("test")

    monkeypatch.setattr(engine, "run_test", fake)
    tools.run_tests(selection=["a::b"], full=True)
    assert captured["selection"] is None


def test_build_lint_delta_maps_all_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake(root, subproject=None, kind=None, timeout=None, use_baseline=True):  # type: ignore[no-untyped-def]
        captured["use_baseline"] = use_baseline
        captured["kind"] = kind
        return NormalizedRun.empty("lint")

    monkeypatch.setattr(engine, "run_check", fake)

    tools.build_lint_delta(kind="lint")
    assert captured["use_baseline"] is True

    tools.build_lint_delta(all=True)
    assert captured["use_baseline"] is False


def test_capture_baseline_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        engine, "capture_baseline", lambda *a, **k: NormalizedRun.empty("baseline")
    )
    env = tools.capture_baseline()
    assert env["command"] == "baseline"
    assert env["status"] == "ok"


def test_clear_baseline_returns_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, "clear_baseline", lambda *a, **k: True)
    assert tools.clear_baseline() == {"cleared": True}
    monkeypatch.setattr(engine, "clear_baseline", lambda *a, **k: False)
    assert tools.clear_baseline() == {"cleared": False}
