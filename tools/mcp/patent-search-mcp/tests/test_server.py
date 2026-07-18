"""Smoke tests for importability and FastMCP tool registration."""

from __future__ import annotations

import asyncio
from typing import Any

import server
from patent_api import PatentInputError


def test_server_imports_and_registers_expected_tools() -> None:
    assert server.mcp.name == "patent-search"
    tools = asyncio.run(server.mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "patent_substructure_search",
        "patent_structure_search_results",
        "patent_metadata",
    }


def test_search_tool_delegates_to_client(monkeypatch: Any) -> None:
    class FakeClient:
        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def search_patents_by_substructure(self, smiles: str, **kwargs: Any) -> dict[str, Any]:
            return {"ok": True, "smiles": smiles, "arguments": kwargs}

    monkeypatch.setattr(server, "SureChEMBLClient", FakeClient)
    result = server.patent_substructure_search(
        "CCO", structure_limit=4, patent_limit=5, wait_seconds=6
    )
    assert result == {
        "ok": True,
        "smiles": "CCO",
        "arguments": {"structure_limit": 4, "patent_limit": 5, "wait_seconds": 6},
    }


def test_tool_returns_structured_input_error(monkeypatch: Any) -> None:
    class FakeClient:
        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def patent_metadata(self, *_: object, **__: object) -> dict[str, Any]:
            raise PatentInputError("bad patent id")

    monkeypatch.setattr(server, "SureChEMBLClient", FakeClient)
    result = server.patent_metadata("bad")
    assert result == {
        "ok": False,
        "status": "error",
        "error_type": "invalid_input",
        "error": "bad patent id",
    }
