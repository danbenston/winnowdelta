"""Phase 5: test-impact running (affected-tests selection + --full)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from winnowdelta.adapters.django_adapter import DjangoAdapter
from winnowdelta.adapters.pytest_adapter import PytestAdapter
from winnowdelta.adapters.vitest_adapter import VitestAdapter
from winnowdelta.cli import _read_selection, build_parser
from winnowdelta.core import engine, runner
from winnowdelta.core.config import Subproject
from winnowdelta.core.model import Status

FIXTURES = Path(__file__).parent / "fixtures"
BASIC = FIXTURES / "pytest_basic"


# --- live pytest: selection actually narrows what runs -----------------------

def test_pytest_runs_only_selected_node() -> None:
    run = PytestAdapter().collect(
        Subproject("default", "pytest"),
        BASIC,
        selection=["test_sample.py::test_fails_equality"],
    )
    assert run.status is Status.FAILED
    # Only the one selected test ran: 1 failure, nothing else collected.
    assert run.summary.total == 1
    assert run.summary.failed == 1
    assert run.failures[0].test_id.endswith("test_fails_equality")


def test_pytest_select_passing_subset_is_ok() -> None:
    run = PytestAdapter().collect(
        Subproject("default", "pytest"),
        BASIC,
        selection=["test_sample.py::test_passes"],
    )
    assert run.status is Status.OK
    assert run.summary.total == 1
    assert run.summary.passed == 1


# --- selection is appended to the runner argv (fake runner) ------------------

class _Capture:
    def __init__(self, content: str):
        self.content = content
        self.argv: list[str] = []

    def __call__(self, command, cwd, env=None, timeout=None):  # type: ignore[no-untyped-def]
        self.argv = list(command)
        try:
            i = command.index("--outputFile")
            Path(command[i + 1]).write_text(self.content, encoding="utf-8")
        except ValueError:
            pass
        return runner.ExecResult(0, "", "", 0.01, False)


_EMPTY_JEST = json.dumps({"testResults": []})


def test_vitest_appends_selection(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    cap = _Capture(_EMPTY_JEST)
    monkeypatch.setattr(runner, "run", cap)
    VitestAdapter().collect(
        Subproject("fe", "vitest"), tmp_path, selection=["src/a.test.ts", "src/b.test.ts"]
    )
    assert "src/a.test.ts" in cap.argv and "src/b.test.ts" in cap.argv
    # selection comes before the reporter flags
    assert cap.argv.index("src/a.test.ts") < cap.argv.index("--reporter=json")


def test_django_appends_labels(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    cap = _Capture("")  # report comes via env; argv capture is what we assert
    monkeypatch.setattr(runner, "run", cap)
    DjangoAdapter().collect(
        Subproject("backend", "django"), tmp_path, selection=["app.tests.T.test_x"]
    )
    assert "app.tests.T.test_x" in cap.argv
    assert any(a.startswith("--testrunner=") for a in cap.argv)


# --- engine + CLI selection semantics ----------------------------------------

def test_engine_empty_selection_is_noop_ok() -> None:
    # Provided-but-empty selection => no impacted tests => clean no-op.
    run = engine.run_test(BASIC, selection=[])
    assert run.status is Status.OK
    assert run.summary.total == 0


def _parse(argv: list[str]):
    return build_parser().parse_args(argv)


def test_read_selection_none_when_unspecified() -> None:
    assert _read_selection(_parse(["test"])) is None


def test_read_selection_full_overrides_only() -> None:
    args = _parse(["test", "--only", "a::b", "--full"])
    assert _read_selection(args) is None


def test_read_selection_from_only() -> None:
    args = _parse(["test", "--only", "a::b", "c::d"])
    assert _read_selection(args) == ["a::b", "c::d"]


def test_read_selection_from_file(tmp_path) -> None:
    f = tmp_path / "sel.txt"
    f.write_text("a::b\n\n c::d \n", encoding="utf-8")
    args = _parse(["test", "--tests-from", str(f)])
    assert _read_selection(args) == ["a::b", "c::d"]
