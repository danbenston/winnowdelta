"""Phase 4: live build/lint deltas against oracle-rex/frontend.

Skipped when that checkout isn't present (e.g. CI). The frontend currently
passes tsc + eslint but has Prettier formatting differences, so an --all check
should surface prettier diagnostics and no tool errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from winnowdelta.core import engine
from winnowdelta.core.model import Status

FRONTEND = Path("D:/Development/PycharmProjects/oracle-rex/frontend")

pytestmark = pytest.mark.skipif(
    not (FRONTEND / "node_modules" / ".bin").exists(),
    reason="oracle-rex/frontend node_modules not available",
)


def test_lint_delta_finds_prettier_diffs() -> None:
    # use_baseline=False writes nothing into the oracle-rex checkout.
    run = engine.run_check(FRONTEND, kind="lint", use_baseline=False, timeout=300)
    assert run.status in (Status.OK, Status.FAILED)
    assert run.error is None
    prettier = [d for d in run.diagnostics if d.rule == "prettier"]
    assert prettier, "expected prettier to report unformatted files"
