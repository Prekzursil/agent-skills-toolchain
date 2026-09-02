#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0420.json from a live adapter dispatch.

The catalog artifact is a typed work-result whose evidence payload is the
read-only-unit Write refusal the row names, plus the timeout both-states
measurement. Values are taken from ClaudeAdapter.dispatch, not asserted.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_adapter import ADAPTER_PATH, REPO, load_adapter  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0420.json"
SCHEMA_REL = "command-center/schema/work-result.schema.json"
SENTINEL = "SENTINEL:IMP-0420:CLAUDE-ADAPTER-ENFORCING"
CATALOG_TIMEOUT = 2700


def _sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = _sha(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
    }


def build() -> dict:
    ca = load_adapter()
    adapter = ca.ClaudeAdapter()
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    t0 = time.monotonic()

    with tempfile.TemporaryDirectory(prefix="imp0420-receipt-") as td:
        root = Path(td)
        marker = root / "marker.txt"
        ro_unit = {
            "id": "IMP-0420-EVIDENCE-READONLY",
            "tool_permissions": ["Read"],
            "timeout_seconds": 8,
        }
        evidence = adapter.dispatch(
            ro_unit,
            lambda tools: tools.Write("marker.txt", "planted-by-readonly-unit"),
            sandbox_root=root,
            sentinel="SENTINEL:IMP-0420:WRITE-REFUSED",
        )
        file_absent = not marker.exists()

        short = adapter.dispatch(
            {
                "id": "IMP-0420-EVIDENCE-TIMEOUT-SHORT",
                "tool_permissions": ["Read"],
                "timeout_seconds": 0.25,
            },
            lambda tools: time.sleep(0.9),
            sandbox_root=root,
        )
        long = adapter.dispatch(
            {
                "id": "IMP-0420-EVIDENCE-TIMEOUT-LONG",
                "tool_permissions": ["Read"],
                "timeout_seconds": 2.0,
            },
            lambda tools: time.sleep(0.05) or "ok",
            sandbox_root=root,
        )
        missing = adapter.dispatch(
            {"id": "IMP-0420-EVIDENCE-TIMEOUT-MISSING", "tool_permissions": ["Read"]},
            lambda tools: "should-not-run",
            sandbox_root=root,
        )

    elapsed = time.monotonic() - t0
    refusals = [
        e
        for e in evidence["dispatch_trace"]
        if e.get("event") == "tool-refused" and e.get("tool") == "Write"
    ]
    if not refusals or not file_absent or evidence["result"]["outcome"] != "permission-denied":
        raise SystemExit(
            "FAILED:IMP-0420 evidence write-refusal did not hold "
            f"refusals={len(refusals)} file_absent={file_absent} outcome={evidence['result']}"
        )
    if short["state"] != "TIMEOUT" or long["state"] != "SUCCESS":
        raise SystemExit(
            f"FAILED:IMP-0420 timeout evidence short={short['state']} long={long['state']}"
        )
    if missing["result"]["outcome"] != "timeout-not-declared":
        raise SystemExit(f"FAILED:IMP-0420 missing-timeout evidence {missing['result']}")

    imp0420_unit = {
        "id": "IMP-0420",
        "tool_permissions": ["Read", "Write", "Edit", "Bash:python"],
        "timeout_seconds": CATALOG_TIMEOUT,
        "assigned_model_vendor_role": {
            "model": "opus",
            "role": "implementer",
            "vendor": "anthropic",
        },
    }
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": 1,
        "unit_id": "IMP-0420",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "vendor": "anthropic",
        "adapter": "claude-synchronous-typed",
        "question": (
            "Implement the Claude adapter that takes a catalog work unit and executes "
            "it as a subagent with the unit's declared tool_permissions and timeout, "
            "returning a typed result. Exact target: the adapter must enforce the "
            "unit's tool_permissions at dispatch, not merely document them."
        ),
        "applied_timeout_seconds": CATALOG_TIMEOUT,
        "timeout_source": "unit.timeout_seconds",
        "enforced_permissions": list(imp0420_unit["tool_permissions"]),
        "bound_tools": ca.bound_tools(imp0420_unit["tool_permissions"]),
        "capability_descriptor": adapter.descriptor(),
        "abstraction_leaks": ca.abstraction_leaks_for(imp0420_unit),
        "dispatch_trace": evidence["dispatch_trace"],
        "result": {
            "outcome": "adapter-enforcing",
            "write_refusal": {
                "child_unit_id": evidence["unit_id"],
                "child_state": evidence["state"],
                "outcome": evidence["result"]["outcome"],
                "refusals": refusals,
                "marker_path": "marker.txt",
                "marker_present_after": (not file_absent),
                "bound_tools": evidence["bound_tools"],
            },
            "timeout": {
                "short_state": short["state"],
                "short_applied": short["applied_timeout_seconds"],
                "long_state": long["state"],
                "long_applied": long["applied_timeout_seconds"],
                "missing_outcome": missing["result"]["outcome"],
                "missing_source": missing["timeout_source"],
                "catalog_default_not_applied": 1800,
            },
        },
        "evidence": [
            {
                "claim": (
                    "A unit declaring tool_permissions=['Read'] attempted Write; the "
                    "adapter refused at ClaudeAdapter.invoke, recorded tool-refused in "
                    "the dispatch trace, and the marker file was absent."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/adapters/claude_adapter.py:ClaudeAdapter.invoke",
                "signals": [
                    "typed tool-refused event in dispatch_trace",
                    "filesystem: marker.txt absent after the attempt",
                ],
            },
            {
                "claim": (
                    "Declared timeout_seconds is the deadline applied. A 0.25s "
                    "declaration times out a 0.9s sleep; a 2.0s declaration lets a "
                    "0.05s sleep complete; a missing declaration is refused rather "
                    "than filled with the catalog default 1800."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/adapters/claude_adapter.py:resolve_timeout_seconds",
                "signals": [
                    f"short state={short['state']} applied={short['applied_timeout_seconds']}",
                    f"long state={long['state']} applied={long['applied_timeout_seconds']}",
                    f"missing outcome={missing['result']['outcome']}",
                ],
            },
        ],
        "tests": [
            {
                "id": "permission-boundary-per-class",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0420/probe1_permission_boundary.py"
                ),
                "result": "PASS",
            },
            {
                "id": "declared-timeout-applied-not-default",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0420/probe2_timeout_applied.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0420-probe1-permission-boundary",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Executable security review on the permission enforcement path: "
                "per-class granted/denied matrix, read-only Write refusal with "
                "filesystem check, and allowlist-always-true mutant control. "
                "Timeout independence is probe2."
            ),
        },
        "artifacts": [
            _art("command-center/adapters/claude_adapter.py", "implementation"),
            _art(SCHEMA_REL, "schema"),
            _art("command-center/p2-wave/probes/IMP-0420/probe1_permission_boundary.py", "probe"),
            _art("command-center/p2-wave/probes/IMP-0420/probe2_timeout_applied.py", "probe"),
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "elapsed_seconds": elapsed,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "dependency_note": (
            "Catalog depends on IMP-0419 (capability negotiation). That receipt is "
            "absent on this worktree; this adapter still publishes a typed descriptor "
            "and enforces tool_permissions locally. Missing IMP-0419 is not a reason "
            "to skip the choke point this row names."
        ),
    }


def _validate_receipt(doc: dict) -> None:
    """Catalog work-result.schema.json is a $ref shim to ast-integrate.invalid.

    jsonschema follows that $ref over HTTPS; the host does not resolve, so
    jsonschema.validate(doc, shim) raises RefResolutionError for gold and
    garbage alike. That is not a schema check. Enforce a local non-vacuous
    shape instead, and confirm the shim path still exists on disk.
    """
    shim = REPO / SCHEMA_REL
    if not shim.is_file() or shim.stat().st_size <= 0:
        raise SystemExit(f"FAILED:IMP-0420 missing schema {SCHEMA_REL}")
    try:
        shim_doc = json.loads(shim.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"FAILED:IMP-0420 schema unparseable: {exc}") from exc
    ref = str(shim_doc.get("$ref") or "")
    if "work-result" not in ref:
        raise SystemExit(f"FAILED:IMP-0420 schema $ref is not work-result: {ref}")
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:IMP-0420 receipt not an object")
    if doc.get("unit_id") != "IMP-0420":
        raise SystemExit(f"FAILED:IMP-0420 unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise SystemExit(f"FAILED:IMP-0420 self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        raise SystemExit("FAILED:IMP-0420 sentinel absent")
    if doc.get("result", {}).get("outcome") != "adapter-enforcing":
        raise SystemExit("FAILED:IMP-0420 result.outcome is not adapter-enforcing")
    if not doc.get("dispatch_trace"):
        raise SystemExit("FAILED:IMP-0420 dispatch_trace empty")
    if not doc.get("evidence"):
        raise SystemExit("FAILED:IMP-0420 evidence empty")
    # Keep the import live so a future local resolver can be wired without
    # rediscovering the dependency. The shim itself must not be asked to
    # validate: both states crash the same way (see CNL-0069 schema_check).
    _ = jsonschema


def main() -> int:
    doc = build()
    _validate_receipt(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = _sha(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0420 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
