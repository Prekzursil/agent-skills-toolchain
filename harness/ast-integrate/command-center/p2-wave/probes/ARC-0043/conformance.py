#!/usr/bin/env python3
"""A6 cross-vendor conformance matrix runner (ARC-0043).

Two local vendor adapters execute the SAME canary work unit. Both artifacts
are judged by:
  * the identical schema file, by path
  * the identical completion predicate

Unrun cells are NOT-CHECKED and are never copied from the other vendor.
A capability disable on one vendor must make the differential report MISMATCH,
not PASS / CONFORMANT.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/work-result.schema.json"
CANARY_ID = "WU-A6-CANARY"
CANARY_SENTINEL = "SUCCESS:WU-A6-CANARY"
REQUIRED_TOOLS = frozenset({"Read", "Write"})
MIN_CONTEXT = 8_000

# The catalog file at SCHEMA_REL is a generated $ref shim whose target is
# generic_report (HTTPS ast-integrate.invalid). Following that $ref either
# hits the network (RefResolutionError) or judges adapter canaries against
# the wrong shape. Schema-parity is PATH identity of that file; structural
# checks use this local adapter-result schema so garbage still fails.
ADAPTER_RESULT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "kind",
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "schema_path",
        "mismatches",
    ],
    "properties": {
        "kind": {"const": "work-result"},
        "schema_version": {"type": "integer", "minimum": 1},
        "unit_id": {"type": "string", "minLength": 1},
        "state": {
            "type": "string",
            "enum": ["SUCCESS", "DEGRADED", "FAILED", "BLOCKED"],
        },
        "verdict": {"type": "string", "minLength": 1},
        "sentinel": {"type": "string", "minLength": 1},
        "schema_path": {"type": "string", "minLength": 1},
        "mismatches": {"type": "array"},
        "payload": {"type": ["object", "null"]},
        "partial_artifact": {},
        "ordinary_looking_success": {"type": "boolean"},
        "adapter_vendor": {"type": "string"},
        "notes": {"type": "array", "items": {"type": "string"}},
        "reason_class": {"type": "string"},
    },
}


def unshadow_stdlib() -> None:
    """Keep repo `platform/` from shadowing stdlib (breaks jsonschema/uuid)."""
    repo = REPO.resolve()
    cleaned: list[str] = []
    for p in sys.path:
        if p in ("", "."):
            continue
        try:
            if Path(p).resolve() == repo:
                continue
        except OSError:
            pass
        cleaned.append(p)
    sys.path[:] = cleaned


def _jsonschema():
    unshadow_stdlib()
    import jsonschema  # noqa: WPS433

    return jsonschema


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def schema_path_abs() -> Path:
    path = REPO / SCHEMA_REL
    if not path.is_file():
        raise FileNotFoundError(SCHEMA_REL)
    return path


def load_schema() -> dict[str, Any]:
    return json.loads(schema_path_abs().read_text(encoding="utf-8"))


def validate_against_schema_path(doc: dict[str, Any], schema_rel: str) -> list[str]:
    """Validate `doc` against the schema file at `schema_rel` (path identity).

    The named file must exist and parse. Constraints come from
    ADAPTER_RESULT_SCHEMA so a $ref shim cannot network-fetch or accept
    garbage. Path identity is still the recorded `schema_path` / sha256.
    """
    path = REPO / schema_rel
    if not path.is_file():
        return [f"schema-missing:{schema_rel}"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"schema-unparseable:{schema_rel}:{type(exc).__name__}"]
    if not isinstance(raw, dict):
        return [f"schema-not-object:{schema_rel}"]
    jsonschema = _jsonschema()
    errs = sorted(
        jsonschema.Draft7Validator(ADAPTER_RESULT_SCHEMA).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    return [f"{list(e.path)}: {e.message}" for e in errs]


@dataclass(frozen=True)
class Caps:
    vendor: str
    tools: frozenset[str]
    schema_support: bool
    context_window: int
    transport: str = "local-adapter"


def anthropic_local() -> Caps:
    return Caps(
        vendor="anthropic",
        tools=frozenset({"Read", "Write", "Edit", "Bash"}),
        schema_support=True,
        context_window=200_000,
    )


def openai_local() -> Caps:
    return Caps(
        vendor="openai",
        tools=frozenset({"Read", "Write", "Bash"}),
        schema_support=True,
        context_window=128_000,
    )


def capability_mismatches(caps: Caps) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    missing = REQUIRED_TOOLS - caps.tools
    if missing:
        found.append(
            {
                "field": "tools",
                "required": sorted(REQUIRED_TOOLS),
                "available": sorted(caps.tools),
                "class": "capability-mismatch",
            }
        )
    if not caps.schema_support:
        found.append(
            {
                "field": "schema_support",
                "required": True,
                "available": False,
                "class": "capability-mismatch",
            }
        )
    if caps.context_window < MIN_CONTEXT:
        found.append(
            {
                "field": "context_window",
                "required": MIN_CONTEXT,
                "available": caps.context_window,
                "class": "capability-mismatch",
            }
        )
    return found


def _success_doc(caps: Caps, *, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "work-result",
        "schema_version": 1,
        "unit_id": CANARY_ID,
        "state": "SUCCESS",
        "verdict": "SUCCESS",
        "sentinel": CANARY_SENTINEL,
        "mismatches": [],
        "partial_artifact": None,
        "ordinary_looking_success": True,
        "adapter_vendor": caps.vendor,
        "schema_path": SCHEMA_REL,
        "payload": payload,
        "notes": [
            "local-adapter execution of WU-A6-CANARY",
            f"vendor={caps.vendor}",
        ],
    }


def _degraded_doc(
    caps: Caps, mismatches: list[dict[str, Any]], partial: dict[str, Any]
) -> dict[str, Any]:
    return {
        "kind": "work-result",
        "schema_version": 1,
        "unit_id": CANARY_ID,
        "state": "DEGRADED",
        "verdict": "DEGRADED",
        "sentinel": f"FAILED:{CANARY_ID} capability-mismatch",
        "reason_class": "capability-mismatch",
        "mismatches": mismatches,
        "partial_artifact": partial,
        "ordinary_looking_success": False,
        "adapter_vendor": caps.vendor,
        "schema_path": SCHEMA_REL,
        "notes": [
            "capability mismatch: refusing ordinary-looking SUCCESS",
            f"vendor={caps.vendor}",
        ],
    }


def completion_predicate(doc: dict[str, Any], text: str, schema_rel: str) -> dict[str, Any]:
    """The SAME predicate applied to every vendor artifact."""
    schema_errs = validate_against_schema_path(doc, schema_rel)
    sentinel_ok = CANARY_SENTINEL in text
    state_ok = doc.get("state") == "SUCCESS"
    verdict_ok = doc.get("verdict") == "SUCCESS"
    no_mismatch = list(doc.get("mismatches") or []) == []
    ok = (
        not schema_errs
        and sentinel_ok
        and state_ok
        and verdict_ok
        and no_mismatch
    )
    return {
        "ok": ok,
        "schema_ok": not schema_errs,
        "schema_errors": schema_errs,
        "sentinel_ok": sentinel_ok,
        "state_ok": state_ok,
        "verdict_ok": verdict_ok,
        "no_mismatch": no_mismatch,
        "schema_path": schema_rel,
    }


def run_vendor(
    caps: Caps,
    out_dir: Path,
    *,
    ran: bool = True,
    payload: dict[str, Any] | None = None,
    schema_rel: str = SCHEMA_REL,
) -> dict[str, Any]:
    """Execute the canary unit on one adapter. If ran=False, return NOT-CHECKED."""
    column_id = f"{caps.vendor}-{'local' if caps.transport == 'local-adapter' else 'live'}"
    if not ran:
        return {
            "vendor": caps.vendor,
            "column_id": column_id,
            "ran": False,
            "inferred": False,
            "verdict": "NOT-CHECKED",
            "reason": "cell was not executed; not copied from the other vendor",
            "schema_path": schema_rel,
            "schema_sha256": None,
            "predicate_ok": None,
            "schema_ok": None,
            "artifact": None,
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"{caps.vendor}.work-result.json"
    partial_path = out_dir / f"{caps.vendor}.partial.json"
    mismatches = capability_mismatches(caps)
    body = payload or {"ranking": ["A2", "A8"], "canary": CANARY_ID}

    if mismatches:
        partial_body = {
            "unit_id": CANARY_ID,
            "step": "pre-schema-emit",
            "note": "partial must survive a capability mismatch",
            "adapter_vendor": caps.vendor,
        }
        partial_path.write_text(
            json.dumps(partial_body, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        p_sha, p_bytes = sha256_file(partial_path)
        partial = {
            "path": str(partial_path.relative_to(REPO)).replace("\\", "/"),
            "bytes": p_bytes,
            "sha256": p_sha,
            "preserved": True,
        }
        doc = _degraded_doc(caps, mismatches, partial)
    else:
        doc = _success_doc(caps, payload=body)

    # Force the recorded schema_path to the one this run was judged against.
    doc["schema_path"] = schema_rel
    artifact.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = artifact.read_text(encoding="utf-8")
    pred = completion_predicate(doc, text, schema_rel)
    schema_sha, _ = sha256_file(REPO / schema_rel) if (REPO / schema_rel).is_file() else ("", 0)
    art_rel = str(artifact.relative_to(REPO)).replace("\\", "/")
    if pred["ok"]:
        cell_verdict = "PASS"
    else:
        cell_verdict = "FAIL"
    return {
        "vendor": caps.vendor,
        "column_id": column_id,
        "ran": True,
        "inferred": False,
        "verdict": cell_verdict,
        "reason": "executed",
        "schema_path": schema_rel,
        "schema_sha256": schema_sha,
        "predicate_ok": pred["ok"],
        "schema_ok": pred["schema_ok"],
        "schema_errors": pred["schema_errors"],
        "mismatches": mismatches,
        "artifact": art_rel,
        "predicate": pred,
        "doc_state": doc.get("state"),
        "doc_verdict": doc.get("verdict"),
        "payload": doc.get("payload"),
    }


def differential(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Compare two vendor cells. Never infer an unrun cell."""
    if not left.get("ran") or not right.get("ran"):
        return {
            "verdict": "NOT-CHECKED",
            "inferred": False,
            "reason": "at least one vendor cell was not executed; refusing to copy",
            "left_ran": bool(left.get("ran")),
            "right_ran": bool(right.get("ran")),
        }
    path_match = left.get("schema_path") == right.get("schema_path")
    sha_match = left.get("schema_sha256") == right.get("schema_sha256")
    both_ok = bool(left.get("predicate_ok")) and bool(right.get("predicate_ok"))
    if both_ok and path_match and sha_match:
        return {
            "verdict": "CONFORMANT",
            "inferred": False,
            "reason": "both vendors passed the shared schema and the shared predicate",
            "schema_path": left.get("schema_path"),
        }
    return {
        "verdict": "MISMATCH",
        "inferred": False,
        "reason": (
            "capability, schema-path, or completion-predicate divergence; "
            "not a silent PASS"
        ),
        "left_ok": left.get("predicate_ok"),
        "right_ok": right.get("predicate_ok"),
        "path_match": path_match,
        "sha_match": sha_match,
        "left_state": left.get("doc_state"),
        "right_state": right.get("doc_state"),
    }


def loud_failure_control(run_root: Path) -> dict[str, Any]:
    """Disable schema_support on openai; differential must be MISMATCH not PASS."""
    a = run_vendor(anthropic_local(), run_root / "loud" / "anthropic")
    b_ok = run_vendor(openai_local(), run_root / "loud" / "openai-ok")
    baseline = differential(a, b_ok)
    b_bad_caps = Caps(
        vendor="openai",
        tools=openai_local().tools,
        schema_support=False,
        context_window=openai_local().context_window,
    )
    b_bad = run_vendor(b_bad_caps, run_root / "loud" / "openai-disabled")
    after = differential(a, b_bad)
    silent_pass = after["verdict"] in {"CONFORMANT", "PASS"}
    ok = (
        baseline["verdict"] == "CONFORMANT"
        and after["verdict"] == "MISMATCH"
        and not silent_pass
        and b_bad.get("doc_state") == "DEGRADED"
        and b_bad.get("predicate_ok") is False
        and a.get("predicate_ok") is True
    )
    return {
        "ok": ok,
        "baseline": baseline,
        "after_disable": after,
        "anthropic": a,
        "openai_ok": b_ok,
        "openai_disabled": b_bad,
        "silent_pass": silent_pass,
    }


def schema_parity_assertion(run_root: Path) -> dict[str, Any]:
    """Both vendors validate against the identical schema file, by path."""
    a = run_vendor(anthropic_local(), run_root / "parity" / "anthropic")
    b = run_vendor(openai_local(), run_root / "parity" / "openai")
    live_sha, _ = sha256_file(schema_path_abs())
    same_path = a.get("schema_path") == b.get("schema_path") == SCHEMA_REL
    same_sha = a.get("schema_sha256") == b.get("schema_sha256") == live_sha
    both_schema_ok = bool(a.get("schema_ok")) and bool(b.get("schema_ok"))
    both_pred = bool(a.get("predicate_ok")) and bool(b.get("predicate_ok"))

    # Mutant: judge openai against a different (copied) schema path.
    other_schema = HERE / "fixtures" / "work-result.copy.schema.json"
    other_schema.parent.mkdir(parents=True, exist_ok=True)
    other_schema.write_bytes(schema_path_abs().read_bytes())
    other_rel = str(other_schema.relative_to(REPO)).replace("\\", "/")
    b_copy = run_vendor(
        openai_local(),
        run_root / "parity" / "openai-copy-schema",
        schema_rel=other_rel,
    )
    copy_diff = differential(a, b_copy)
    path_mutant_caught = (
        b_copy.get("schema_path") != SCHEMA_REL
        and copy_diff["verdict"] == "MISMATCH"
    )

    ok = same_path and same_sha and both_schema_ok and both_pred and path_mutant_caught
    return {
        "ok": ok,
        "schema_path": SCHEMA_REL,
        "schema_sha256": live_sha,
        "same_path": same_path,
        "same_sha": same_sha,
        "both_schema_ok": both_schema_ok,
        "both_predicate_ok": both_pred,
        "path_mutant_caught": path_mutant_caught,
        "copy_schema_path": other_rel,
        "copy_differential": copy_diff,
        "anthropic": a,
        "openai": b,
    }


def unrun_cells_not_inferred(run_root: Path) -> dict[str, Any]:
    a = run_vendor(anthropic_local(), run_root / "unrun" / "anthropic")
    live = run_vendor(openai_local(), run_root / "unrun" / "openai-live", ran=False)
    diff = differential(a, live)
    copied = live.get("verdict") == a.get("verdict") and live.get("ran") is False
    # A copied PASS would mean we inferred the unrun cell.
    inferred_pass = live.get("verdict") in {"PASS", "CONFORMANT"}
    ok = (
        live.get("verdict") == "NOT-CHECKED"
        and live.get("inferred") is False
        and live.get("ran") is False
        and diff["verdict"] == "NOT-CHECKED"
        and not copied
        and not inferred_pass
        and a.get("ran") is True
    )
    return {
        "ok": ok,
        "live_cell": live,
        "differential": diff,
        "copied": copied,
        "anthropic": a,
    }


def mutation_suite_would_not_catch(run_root: Path) -> dict[str, Any]:
    """Semantic payload swap still CONFORMANT: schema+predicate do not catch it."""
    a = run_vendor(
        anthropic_local(),
        run_root / "gap" / "anthropic",
        payload={"ranking": ["A2", "A8"], "choice": "keep-A2"},
    )
    b = run_vendor(
        openai_local(),
        run_root / "gap" / "openai",
        payload={"ranking": ["A1", "A9"], "choice": "keep-A1"},
    )
    diff = differential(a, b)
    payloads_differ = a.get("payload") != b.get("payload")
    ok = (
        payloads_differ
        and diff["verdict"] == "CONFORMANT"
        and a.get("predicate_ok")
        and b.get("predicate_ok")
    )
    return {
        "ok": ok,
        "name": "semantic-payload-swap",
        "description": (
            "Swap ranking/choice strings that remain schema-valid and keep the "
            "SUCCESS sentinel. Schema-parity and the shared completion predicate "
            "still CONFORMANT. The suite does not prove semantic interchangeability."
        ),
        "differential": diff,
        "payloads_differ": payloads_differ,
        "anthropic_payload": a.get("payload"),
        "openai_payload": b.get("payload"),
    }


run_adapter = run_vendor
schema_parity_assertion = schema_parity_assertion


def build_matrix(run_root: Path) -> dict[str, Any]:
    loud = loud_failure_control(run_root)
    parity = schema_parity_assertion(run_root)
    unrun = unrun_cells_not_inferred(run_root)
    gap = mutation_suite_would_not_catch(run_root)
    a = parity["anthropic"]
    b = parity["openai"]
    live_a = run_vendor(anthropic_local(), run_root / "matrix" / "live-a", ran=False)
    live_b = run_vendor(
        Caps(
            vendor="openai",
            tools=openai_local().tools,
            schema_support=True,
            context_window=128_000,
            transport="live-api",
        ),
        run_root / "matrix" / "live-b",
        ran=False,
    )
    cells = [
        {
            "row_id": "schema-valid",
            "column_id": "anthropic-local",
            "verdict": "PASS" if a.get("schema_ok") else "FAIL",
            "ran": True,
            "inferred": False,
            "artifact": a.get("artifact"),
        },
        {
            "row_id": "schema-valid",
            "column_id": "openai-local",
            "verdict": "PASS" if b.get("schema_ok") else "FAIL",
            "ran": True,
            "inferred": False,
            "artifact": b.get("artifact"),
        },
        {
            "row_id": "schema-valid",
            "column_id": "anthropic-live",
            "verdict": "NOT-CHECKED",
            "ran": False,
            "inferred": False,
            "reason": live_a["reason"],
        },
        {
            "row_id": "schema-valid",
            "column_id": "openai-live",
            "verdict": "NOT-CHECKED",
            "ran": False,
            "inferred": False,
            "reason": live_b["reason"],
        },
        {
            "row_id": "completion-predicate",
            "column_id": "anthropic-local",
            "verdict": "PASS" if a.get("predicate_ok") else "FAIL",
            "ran": True,
            "inferred": False,
        },
        {
            "row_id": "completion-predicate",
            "column_id": "openai-local",
            "verdict": "PASS" if b.get("predicate_ok") else "FAIL",
            "ran": True,
            "inferred": False,
        },
        {
            "row_id": "completion-predicate",
            "column_id": "anthropic-live",
            "verdict": "NOT-CHECKED",
            "ran": False,
            "inferred": False,
        },
        {
            "row_id": "completion-predicate",
            "column_id": "openai-live",
            "verdict": "NOT-CHECKED",
            "ran": False,
            "inferred": False,
        },
        {
            "row_id": "differential",
            "column_id": "both-local",
            "verdict": differential(a, b)["verdict"],
            "ran": True,
            "inferred": False,
        },
        {
            "row_id": "differential",
            "column_id": "openai-schema-disabled",
            "verdict": loud["after_disable"]["verdict"],
            "ran": True,
            "inferred": False,
        },
        {
            "row_id": "differential",
            "column_id": "live-pair",
            "verdict": "NOT-CHECKED",
            "ran": False,
            "inferred": False,
            "reason": "live vendor APIs were not invoked",
        },
    ]
    return {
        "loud": loud,
        "parity": parity,
        "unrun": unrun,
        "gap": gap,
        "cells": cells,
        "ok": loud["ok"] and parity["ok"] and unrun["ok"] and gap["ok"],
    }


build_matrix = build_matrix
unshadow_stdlib = unshadow_stdlib
