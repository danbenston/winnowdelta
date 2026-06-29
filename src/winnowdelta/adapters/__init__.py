"""Per-framework adapters.

Importing this package registers all built-in adapters into the
``core.adapter`` registry (import side effect). The engine imports it once to
make adapters discoverable by stack name.
"""

from . import pytest_adapter  # noqa: F401  (registration side effect)

__all__ = ["pytest_adapter"]
