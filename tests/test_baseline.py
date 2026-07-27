"""Phase 4: baseline store + position-insensitive multiset delta."""

from __future__ import annotations

import pytest

from winnowdelta.core import config, engine
from winnowdelta.core.baseline import BaselineStore, diff_diagnostics
from winnowdelta.core.model import Diagnostic, Status


def _d(file: str, rule: str, msg: str, line: int | None = None) -> Diagnostic:
    return Diagnostic(file=file, severity="error", message=msg, rule=rule, line=line)


def test_only_new_diagnostics_returned() -> None:
    baseline = [_d("a.ts", "TS1", "old", line=1)]
    current = [
        _d("a.ts", "TS1", "old", line=5),   # same fingerprint, moved line -> not new
        _d("b.ts", "TS2", "fresh", line=3),  # genuinely new
    ]
    new = diff_diagnostics(current, baseline)
    assert len(new) == 1
    assert new[0].file == "b.ts"
    assert new[0].message == "fresh"


def test_line_shift_does_not_flag_preexisting() -> None:
    baseline = [_d("a.ts", "R", "warn", line=10)]
    current = [_d("a.ts", "R", "warn", line=42)]
    assert diff_diagnostics(current, baseline) == []


def test_added_duplicate_occurrence_is_new() -> None:
    baseline = [_d("a.ts", "R", "dup", line=1)]
    current = [_d("a.ts", "R", "dup", line=1), _d("a.ts", "R", "dup", line=2)]
    new = diff_diagnostics(current, baseline)
    assert len(new) == 1  # one pre-existing consumed, the second is new


def test_empty_baseline_means_all_new() -> None:
    current = [_d("a.ts", "R", "x"), _d("b.ts", "R", "y")]
    assert diff_diagnostics(current, []) == current


def test_store_roundtrip(tmp_path) -> None:
    store = BaselineStore(tmp_path)
    assert not store.exists("frontend")
    assert store.load("frontend") == []

    diags = [_d("a.ts", "TS1", "boom", line=3)]
    store.save("frontend", diags)
    assert store.exists("frontend")

    loaded = store.load("frontend")
    assert loaded == diags  # frozen dataclass equality


def test_store_clear(tmp_path) -> None:
    store = BaselineStore(tmp_path)
    store.save("x", [_d("a", "R", "m")])
    assert store.clear("x") is True
    assert store.clear("x") is False


def test_store_keys_by_subproject(tmp_path) -> None:
    store = BaselineStore(tmp_path)
    store.save("backend", [_d("a.py", "R", "one")])
    store.save("frontend", [_d("a.ts", "R", "two")])
    assert store.load("backend")[0].message == "one"
    assert store.load("frontend")[0].message == "two"


@pytest.mark.parametrize(
    "content",
    [
        "not json{",              # truncated / corrupt
        "",                       # zero-length (interrupted write)
        '{"diagnostics": null}',  # right shape, wrong type
        '{"other": []}',          # missing key
        '{"diagnostics": [{"unexpected": 1}]}',  # schema drift
    ],
    ids=["corrupt", "empty", "null", "missing-key", "schema-drift"],
)
def test_unreadable_baseline_reads_as_absent(tmp_path, content: str) -> None:
    """An unreadable baseline must degrade to "no baseline", never raise.

    engine.run_check promises callers always get a NormalizedRun; an exception
    from here tracebacks out of both the CLI and the MCP server instead.
    """
    store = BaselineStore(tmp_path)
    store.save("x", [_d("a.ts", "R", "m")])
    store._path("x").write_text(content, encoding="utf-8")
    assert store.load("x") == []


def test_check_survives_a_corrupt_baseline(tmp_path) -> None:
    (tmp_path / config.CONFIG_NAME).write_text(
        '[subproject.x]\nstack = "vitest"\ntools = []\n', encoding="utf-8"
    )
    BaselineStore(tmp_path)._path("x").parent.mkdir(parents=True, exist_ok=True)
    BaselineStore(tmp_path)._path("x").write_text("{corrupt", encoding="utf-8")

    run = engine.run_check(tmp_path)
    assert run.status is Status.OK  # no tools configured, and no crash


def test_save_is_atomic_and_leaves_no_temp_files(tmp_path) -> None:
    store = BaselineStore(tmp_path)
    store.save("x", [_d("a.ts", "R", "m")])
    store.save("x", [_d("b.ts", "R", "n")])
    assert [p.name for p in store.dir.iterdir()] == ["x.json"]
    assert store.load("x")[0].file == "b.ts"
