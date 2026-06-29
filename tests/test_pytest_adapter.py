"""Phase 2: pytest adapter + engine (actually spawns pytest on fixture repos)."""

from __future__ import annotations

from pathlib import Path

from winnowdelta.adapters.pytest_adapter import PytestAdapter
from winnowdelta.core import engine
from winnowdelta.core.config import Subproject
from winnowdelta.core.model import Status

FIXTURES = Path(__file__).parent / "fixtures"
BASIC = FIXTURES / "pytest_basic"
PASS = FIXTURES / "pytest_pass"


def _sub() -> Subproject:
    return Subproject(name="default", stack="pytest")


def test_adapter_reports_only_failures() -> None:
    run = PytestAdapter().collect(_sub(), BASIC)
    assert run.status is Status.FAILED
    assert run.summary.passed == 1
    assert run.summary.skipped == 1
    assert run.summary.failed == 2

    ids = {f.test_id for f in run.failures}
    assert any("test_fails_equality" in i for i in ids)
    assert any("test_errors" in i for i in ids)


def test_adapter_relativizes_crash_paths_to_cwd() -> None:
    run = PytestAdapter().collect(_sub(), BASIC)
    failing = next(f for f in run.failures if "test_fails_equality" in f.test_id)
    # base=cwd, so the absolute crash path collapses to the bare fixture file.
    assert failing.file == "test_sample.py"
    assert failing.line == 7
    assert failing.received == "2" and failing.expected == "3"


def test_adapter_all_pass_is_ok() -> None:
    run = PytestAdapter().collect(_sub(), PASS)
    assert run.status is Status.OK
    assert run.failures == []
    assert run.summary.passed == 2


def test_engine_autodetects_and_runs() -> None:
    run = engine.run_test(PASS)
    assert run.status is Status.OK
    assert run.summary.passed == 2


def test_engine_no_stack_is_error(tmp_path) -> None:
    run = engine.run_test(tmp_path)
    assert run.status is Status.ERROR
    assert run.error is not None


def test_engine_unknown_subproject_is_error() -> None:
    run = engine.run_test(PASS, subproject="nonexistent")
    assert run.status is Status.ERROR
    assert "nonexistent" in (run.error or "")
