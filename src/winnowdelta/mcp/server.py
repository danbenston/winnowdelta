"""MCP server exposing winnowdelta over stdio.

Thin FastMCP wrapper around the pure functions in ``tools.py`` (which hold the
logic and the docstrings the agent sees). Run with ``winnowdelta-mcp`` or
``python -m winnowdelta.mcp.server``.

Requires the ``mcp`` extra: ``pip install "winnowdelta[mcp]"``.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import tools


def build_server() -> FastMCP:
    server = FastMCP("winnowdelta")
    server.tool()(tools.run_tests)
    server.tool()(tools.build_lint_delta)
    server.tool()(tools.capture_baseline)
    server.tool()(tools.clear_baseline)
    return server


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
