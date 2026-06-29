"""Phase 6: MCP server registration (requires the mcp SDK)."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp", reason="mcp extra not installed")

from winnowdelta.mcp.server import build_server  # noqa: E402


def test_server_registers_all_tools() -> None:
    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == {"run_tests", "build_lint_delta", "capture_baseline", "clear_baseline"}


def test_run_tests_schema_exposes_selection_and_full() -> None:
    server = build_server()
    tools = asyncio.run(server.list_tools())
    run_tests = next(t for t in tools if t.name == "run_tests")
    props = set(run_tests.inputSchema.get("properties", {}))
    assert {"selection", "full", "subproject", "timeout", "root"} <= props


def test_tool_descriptions_present() -> None:
    server = build_server()
    tools = asyncio.run(server.list_tools())
    for t in tools:
        assert t.description, f"{t.name} has no description"


def test_call_tool_run_tests_roundtrip() -> None:
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "pytest_basic"
    server = build_server()
    result = asyncio.run(server.call_tool("run_tests", {"root": str(fixture)}))

    # FastMCP returns (content_list, structured_dict); older versions a list.
    if isinstance(result, tuple):
        content, structured = result
        env = structured
    else:
        content, env = result, json.loads(result[0].text)

    assert env["status"] == "failed"
    assert len(env["failures"]) == 2
    assert content[0].text  # also surfaced as text content
