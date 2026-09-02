"""Shared IMP-0426 scenario: adapter-boundary gate over the fixture vendor."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATE_DIR = REPO / "tools" / "command-center"
if str(GATE_DIR) not in sys.path:
    sys.path.insert(0, str(GATE_DIR))

import output_schema_gate as gate  # noqa: E402

VENDOR_CLI = HERE / "vendor_cli.py"
TYPED_SCHEMA = (
    "command-center/p2-wave/probes/IMP-0426/fixtures/typed.schema.json"
)
MCP_INVENTORY = HERE / "fixtures" / "mcp-inventory.json"

FIXTURE_UNIT = {
    "id": "FIX-0001",
    "output_schema": TYPED_SCHEMA,
    "output_path": "command-center/p2-wave/probes/IMP-0426/.work/out.json",
}


def argv_has_ignore(attempts: list[dict[str, Any]]) -> bool:
    for att in attempts:
        argv = [str(x) for x in (att.get("argv") or [])]
        if "--ignore-user-config" in argv:
            return True
    return False


def run_valid(*, workdir: Path) -> dict[str, Any]:
    seen: list[dict[str, Any]] = []

    def consumer(payload: dict[str, Any]) -> None:
        seen.append(payload)

    result = gate.dispatch(
        FIXTURE_UNIT,
        repo=REPO,
        workdir=workdir,
        vendor_cli=VENDOR_CLI,
        mcp_inventory=None,
        ignore_user_config=True,
        emit_invalid=False,
        allow_mcp_retry=False,
        consumer=consumer,
    )
    result["consumer_payloads"] = seen
    return result


def run_schema_invalid(*, workdir: Path) -> dict[str, Any]:
    seen: list[dict[str, Any]] = []

    def consumer(payload: dict[str, Any]) -> None:
        seen.append(payload)

    result = gate.dispatch(
        FIXTURE_UNIT,
        repo=REPO,
        workdir=workdir,
        vendor_cli=VENDOR_CLI,
        mcp_inventory=None,
        ignore_user_config=True,
        emit_invalid=True,
        allow_mcp_retry=True,
        consumer=consumer,
    )
    result["consumer_payloads"] = seen
    return result


def run_mcp_active(*, workdir: Path, allow_mcp_retry: bool) -> dict[str, Any]:
    seen: list[dict[str, Any]] = []

    def consumer(payload: dict[str, Any]) -> None:
        seen.append(payload)

    result = gate.dispatch(
        FIXTURE_UNIT,
        repo=REPO,
        workdir=workdir,
        vendor_cli=VENDOR_CLI,
        mcp_inventory=MCP_INVENTORY,
        ignore_user_config=False,
        emit_invalid=False,
        allow_mcp_retry=allow_mcp_retry,
        consumer=consumer,
    )
    result["consumer_payloads"] = seen
    return result


def run_ignore_user_config(*, workdir: Path) -> dict[str, Any]:
    seen: list[dict[str, Any]] = []

    def consumer(payload: dict[str, Any]) -> None:
        seen.append(payload)

    result = gate.dispatch(
        FIXTURE_UNIT,
        repo=REPO,
        workdir=workdir,
        vendor_cli=VENDOR_CLI,
        mcp_inventory=MCP_INVENTORY,
        ignore_user_config=True,
        emit_invalid=False,
        allow_mcp_retry=False,
        consumer=consumer,
    )
    result["consumer_payloads"] = seen
    return result
