"""Phase 4: baseline store + position-insensitive multiset delta."""

from __future__ import annotations

from winnowdelta.core.baseline import BaselineStore, diff_diagnostics
from winnowdelta.core.model import Diagnostic


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
