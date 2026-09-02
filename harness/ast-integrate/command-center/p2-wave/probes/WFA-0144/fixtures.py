"""Scout-candidate, corpus, and goal fixtures for WFA-0144.

WFA-0143 (scout), WFA-0129 (matched-case corpus) and WFA-0132 (tournament
runner) are not delivered on this worktree. These fixtures are explicit
stand-ins: they encode the *shapes* those units would emit, not a claim
that those units ran.
"""
from __future__ import annotations

import copy
import json
from typing import Any

# --- Goals -----------------------------------------------------------------

ADOPTION_GOAL: dict[str, Any] = {
    "id": "goal.json-ingest-receipt",
    "statement": (
        "Ingest a JSON payload, validate it against a required-field schema, "
        "and emit a receipt."
    ),
    "required_ops": ["parse-json", "schema-validate", "emit-receipt"],
    "required_tags": ["parse-json", "schema-validate", "emit-receipt"],
    "constraints": {"license": ["MIT", "Apache-2.0", "BSD-3-Clause"]},
}

UNCOVERED_GOAL: dict[str, Any] = {
    "id": "goal.stream-fuse-lineage",
    "statement": (
        "Split a record stream, fuse the parts under a certification flag, "
        "and persist a lineage record."
    ),
    "required_ops": ["stream-split", "fuse-certified", "lineage-record"],
    "required_tags": ["stream-split", "fuse-certified", "lineage-record"],
    "constraints": {"license": ["MIT", "Apache-2.0", "BSD-3-Clause"]},
}

GOALS = {g["id"]: g for g in (ADOPTION_GOAL, UNCOVERED_GOAL)}

# --- Scout candidates (WFA-0143 stand-in) ----------------------------------

CANDIDATES: list[dict[str, Any]] = [
    {
        "id": "wf.json-ingest-v3",
        "title": "JSON ingest with schema receipt",
        "license": "MIT",
        "maintenance": "active",
        "scout_rank": 1,
        "provenance": "fixture://scout/local-registry/wf.json-ingest-v3",
        "coverage_tags": ["parse-json", "schema-validate", "emit-receipt"],
        "mechanisms": [
            {
                "id": "mech.parse-json",
                "op": "parse-json",
                "kind": "parse",
                "transferable": True,
            },
            {
                "id": "mech.schema-validate",
                "op": "schema-validate",
                "kind": "validate",
                "transferable": True,
            },
            {
                "id": "mech.emit-receipt",
                "op": "emit-receipt",
                "kind": "emit",
                "transferable": True,
            },
        ],
        "stages": [
            {"id": "s1", "op": "parse-json", "mechanism_id": "mech.parse-json"},
            {"id": "s2", "op": "schema-validate", "mechanism_id": "mech.schema-validate"},
            {"id": "s3", "op": "emit-receipt", "mechanism_id": "mech.emit-receipt"},
        ],
    },
    {
        "id": "wf.vendor-locked-etl",
        "title": "Vendor ETL that also ingests JSON (unlicensed twin)",
        "license": "UNLICENSED",
        "maintenance": "active",
        "scout_rank": 2,
        "provenance": "fixture://scout/marketplace/wf.vendor-locked-etl",
        "coverage_tags": ["parse-json", "schema-validate", "emit-receipt"],
        "mechanisms": [
            {
                "id": "mech.vendor.parse",
                "op": "parse-json",
                "kind": "parse",
                "transferable": False,
                "reason": "license-unknown",
            },
            {
                "id": "mech.vendor.validate",
                "op": "schema-validate",
                "kind": "validate",
                "transferable": False,
                "reason": "license-unknown",
            },
            {
                "id": "mech.vendor.receipt",
                "op": "emit-receipt",
                "kind": "emit",
                "transferable": False,
                "reason": "license-unknown",
            },
        ],
        "stages": [
            {"id": "v1", "op": "parse-json", "mechanism_id": "mech.vendor.parse"},
            {"id": "v2", "op": "schema-validate", "mechanism_id": "mech.vendor.validate"},
            {"id": "v3", "op": "emit-receipt", "mechanism_id": "mech.vendor.receipt"},
        ],
    },
    {
        "id": "wf.stream-split-v1",
        "title": "Stream splitter",
        "license": "Apache-2.0",
        "maintenance": "active",
        "scout_rank": 3,
        "provenance": "fixture://scout/local-registry/wf.stream-split-v1",
        "coverage_tags": ["stream-split"],
        "mechanisms": [
            {
                "id": "mech.stream-split",
                "op": "stream-split",
                "kind": "split",
                "transferable": True,
            }
        ],
        "stages": [
            {"id": "t1", "op": "stream-split", "mechanism_id": "mech.stream-split"},
        ],
    },
    {
        "id": "wf.fuse-cert-v1",
        "title": "Certified fuse with lineage",
        "license": "MIT",
        "maintenance": "active",
        "scout_rank": 4,
        "provenance": "fixture://scout/local-registry/wf.fuse-cert-v1",
        "coverage_tags": ["fuse-certified", "lineage-record"],
        "mechanisms": [
            {
                "id": "mech.fuse-certified",
                "op": "fuse-certified",
                "kind": "fuse",
                "transferable": True,
            },
            {
                "id": "mech.lineage-record",
                "op": "lineage-record",
                "kind": "lineage",
                "transferable": True,
            },
        ],
        "stages": [
            {"id": "f1", "op": "fuse-certified", "mechanism_id": "mech.fuse-certified"},
            {"id": "f2", "op": "lineage-record", "mechanism_id": "mech.lineage-record"},
        ],
    },
    {
        "id": "wf.retry-shell",
        "title": "Generic retry wrapper (no ingest / no stream coverage)",
        "license": "BSD-3-Clause",
        "maintenance": "stale",
        "scout_rank": 5,
        "provenance": "fixture://scout/docs/wf.retry-shell",
        "coverage_tags": ["retry-until"],
        "mechanisms": [
            {
                "id": "mech.retry-until",
                "op": "retry-until",
                "kind": "control",
                "transferable": True,
            }
        ],
        "stages": [
            {"id": "r1", "op": "retry-until", "mechanism_id": "mech.retry-until"},
        ],
    },
]

COMPOSE_COMPATIBLE = {("wf.stream-split-v1", "wf.fuse-cert-v1")}

# --- WFA-0129-style matched-case corpus (stand-in) --------------------------

CORPUS: list[dict[str, Any]] = [
    {
        "id": "c.json.ok",
        "goal_id": "goal.json-ingest-receipt",
        "tags": ["parse-json", "schema-validate", "emit-receipt"],
        "input": {"raw": '{"name":"ok","n":1}'},
        "expect": {"ok": True, "receipt": True},
    },
    {
        "id": "c.json.bad",
        "goal_id": "goal.json-ingest-receipt",
        "tags": ["parse-json", "schema-validate", "emit-receipt"],
        "input": {"raw": "NOTJSON"},
        "expect": {"ok": False, "error": "parse-error"},
    },
    {
        "id": "c.json.missing",
        "goal_id": "goal.json-ingest-receipt",
        "tags": ["parse-json", "schema-validate", "emit-receipt"],
        "input": {"raw": '{"n":1}'},
        "expect": {"ok": False, "error": "schema-error"},
    },
    {
        "id": "c.stream.ok",
        "goal_id": "goal.stream-fuse-lineage",
        "tags": ["stream-split", "fuse-certified", "lineage-record"],
        "input": {"items": [{"id": "a", "v": 1}, {"id": "b", "v": 2}]},
        "expect": {"ok": True, "fused": True, "lineage": True},
    },
    {
        "id": "c.stream.empty",
        "goal_id": "goal.stream-fuse-lineage",
        "tags": ["stream-split", "fuse-certified", "lineage-record"],
        "input": {"items": []},
        "expect": {"ok": False, "error": "empty-stream"},
    },
]


def cases_for(goal_id: str) -> list[dict[str, Any]]:
    return [copy.deepcopy(c) for c in CORPUS if c["goal_id"] == goal_id]


def candidate_by_id(cid: str) -> dict[str, Any]:
    for c in CANDIDATES:
        if c["id"] == cid:
            return copy.deepcopy(c)
    raise KeyError(cid)


# --- Executable ops (tiny interpreter) -------------------------------------

def op_parse_json(ctx: dict[str, Any]) -> dict[str, Any]:
    if ctx.get("error"):
        return ctx
    raw = (ctx.get("input") or {}).get("raw")
    if raw is None:
        ctx["error"] = "parse-error"
        return ctx
    try:
        ctx["doc"] = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        ctx["error"] = "parse-error"
    return ctx


def op_schema_validate(ctx: dict[str, Any]) -> dict[str, Any]:
    if ctx.get("error"):
        return ctx
    doc = ctx.get("doc")
    if not isinstance(doc, dict) or "name" not in doc:
        ctx["error"] = "schema-error"
    return ctx


def op_emit_receipt(ctx: dict[str, Any]) -> dict[str, Any]:
    if ctx.get("error"):
        ctx["ok"] = False
        ctx["output"] = {"ok": False, "error": ctx["error"]}
        return ctx
    ctx["ok"] = True
    ctx["receipt"] = True
    ctx["output"] = {"ok": True, "receipt": True, "doc": ctx.get("doc")}
    return ctx


def op_stream_split(ctx: dict[str, Any]) -> dict[str, Any]:
    if ctx.get("error"):
        return ctx
    items = (ctx.get("input") or {}).get("items")
    if not items:
        ctx["error"] = "empty-stream"
        return ctx
    ctx["parts"] = list(items)
    return ctx


def op_fuse_certified(ctx: dict[str, Any]) -> dict[str, Any]:
    if ctx.get("error"):
        return ctx
    if "parts" not in ctx:
        ctx["error"] = "missing-parts"
        return ctx
    parts = ctx["parts"]
    ctx["fused"] = True
    ctx["fused_payload"] = {"count": len(parts), "ids": [p.get("id") for p in parts]}
    return ctx


def op_lineage_record(ctx: dict[str, Any]) -> dict[str, Any]:
    if ctx.get("error"):
        ctx["ok"] = False
        ctx["output"] = {"ok": False, "error": ctx["error"]}
        return ctx
    ctx["lineage"] = True
    ctx["ok"] = True
    ctx["output"] = {
        "ok": True,
        "fused": True,
        "lineage": True,
        "payload": ctx.get("fused_payload"),
    }
    return ctx


def op_retry_until(ctx: dict[str, Any]) -> dict[str, Any]:
    """No-op control stage: does not satisfy ingest or stream cases."""
    return ctx


OPS: dict[str, Any] = {
    "parse-json": op_parse_json,
    "schema-validate": op_schema_validate,
    "emit-receipt": op_emit_receipt,
    "stream-split": op_stream_split,
    "fuse-certified": op_fuse_certified,
    "lineage-record": op_lineage_record,
    "retry-until": op_retry_until,
}

LOOKS_RIGHT_OP = "looks-right"
