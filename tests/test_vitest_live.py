"""Phase 3: live Vitest integration against oracle-rex/frontend.

Skipped automatically when that checkout (with installed node_modules) is not
present — e.g. on CI. This is the real end-to-end smoke that the adapter drives
the npm shim and parses Vitest 4's JSON on Windows.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from winnowdelta.adapters.vitest_adapter import VitestAdapter
from winnowdelta.core.config import Subproject
from winnowdelta.core.model import Status

FRONTEND = Path("D:/Development/PycharmProjects/oracle-rex/frontend")

pytestmark = pytest.mark.skipif(
    not (FRONTEND / "node_modules" / ".bin").exists(),
    reason="oracle-rex/frontend node_modules not available",
)


def test_vitest_runs_real_suite() -> None:
    run = VitestAdapter().collect(Subproject("frontend", "vitest"), FRONTEND, timeout=300)
    # The suite currently passes; we assert it ran and parsed, not a specific count.
    assert run.status in (Status.OK, Status.FAILED)
    assert run.summary.total > 0
    if run.status is Status.OK:
        assert run.failures == []
