"""Per-unit output-schema gate at the vendor boundary (IMP-0426)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

CLASS_OK = "ok"
CLASS_SCHEMA_INVALID = "schema-invalid"
CLASS_MCP = "typed-schema-mcp-interaction"


def decide_retry(classification: str, retries_used: int, allow_mcp_retry: bool) -> str | None:
    if classification == CLASS_SCHEMA_INVALID:
        return None
    if classification == CLASS_MCP and retries_used == 0 and allow_mcp_retry:
        return "ignore-user-config"
    return None


def _run_vendor(
    vendor_cli: Path,
    *,
    workdir: Path,
    unit: dict[str, Any],
    repo: Path,
    mcp_inventory: Path | None,
    ignore_user_config: bool,
    emit_invalid: bool,
) -> dict[str, Any]:
    workdir.mkdir(parents=True, exist_ok=True)
    prompt = workdir / "prompt.txt"
    prompt.write_text("typed output please\n", encoding="utf-8")
    out = workdir / "last.json"
    schema = repo / str(unit.get("output_schema") or "")
    argv = [
        sys.executable,
        "-B",
        str(vendor_cli),
        "--prompt-file",
        str(prompt),
        "--output-last-message",
        str(out),
        "--output-schema",
        str(schema),
        "--unit-id",
        str(unit.get("id") or "FIX"),
    ]
    if mcp_inventory is not None:
        argv.extend(["--mcp-inventory", str(mcp_inventory)])
    if ignore_user_config:
        argv.append("--ignore-user-config")
    if emit_invalid:
        argv.append("--emit-invalid")
    proc = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True)
    return {
        "argv": argv,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "output_path": out,
    }


def dispatch(
    unit: dict[str, Any],
    *,
    repo: Path,
    workdir: Path,
    vendor_cli: Path,
    mcp_inventory: Path | None = None,
    ignore_user_config: bool = False,
    emit_invalid: bool = False,
    allow_mcp_retry: bool = False,
    consumer: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    attempts = []
    retries_used = 0
    ignore = ignore_user_config
    classification = CLASS_OK
    payload = None
    consumer_invoked = False
    errors: list[str] = []
    while True:
        att = _run_vendor(
            vendor_cli,
            workdir=workdir / f"attempt-{len(attempts)}",
            unit=unit,
            repo=repo,
            mcp_inventory=mcp_inventory,
            ignore_user_config=ignore,
            emit_invalid=emit_invalid,
        )
        attempts.append(att)
        stderr = att.get("stderr") or ""
        rc = int(att.get("returncode") or 0)
        if "CLASSIFICATION:typed-schema-mcp-interaction" in stderr or rc == 3:
            classification = CLASS_MCP
            action = decide_retry(classification, retries_used, allow_mcp_retry)
            if action == "ignore-user-config":
                retries_used += 1
                ignore = True
                continue
            break
        out_path = Path(att["output_path"])
        if out_path.is_file():
            try:
                payload = json.loads(out_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = None
                classification = CLASS_SCHEMA_INVALID
                errors.append("unparseable")
                break
        schema_path = repo / str(unit.get("output_schema") or "")
        valid = False
        if payload is not None and schema_path.is_file():
            try:
                import jsonschema

                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                jsonschema.validate(payload, schema)
                valid = True
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
                valid = False
        if not valid:
            classification = CLASS_SCHEMA_INVALID
            break
        classification = CLASS_OK
        if consumer is not None:
            consumer(payload)
            consumer_invoked = True
        break

    ok = classification == CLASS_OK
    return {
        "terminal_kind": "SUCCESS" if ok else "FAILED",
        "schema_gate": {
            "classification": classification,
            "valid": ok,
            "enforced": True,
            "retries_used": retries_used,
            "consumer_invoked": consumer_invoked,
            "errors": errors,
        },
        "attempts": attempts,
        "classification": classification,
    }
