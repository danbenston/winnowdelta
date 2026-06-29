"""Per-framework adapters.

Importing this package registers all built-in adapters into the
``core.adapter`` registry (import side effect). The engine imports it once to
make adapters discoverable by stack name.
"""

from . import (  # noqa: F401  (registration side effects)
    django_adapter,
    jest_adapter,
    pytest_adapter,
    vitest_adapter,
)

__all__ = ["django_adapter", "jest_adapter", "pytest_adapter", "vitest_adapter"]
