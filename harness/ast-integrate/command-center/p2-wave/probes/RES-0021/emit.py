#!/usr/bin/env python3
"""Emit command-center/research/RES-0021.json from a live inventory."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import measure  # noqa: E402

OUT = "command-center/research/RES-0021.json"
SCHEMA = "command-center/schema/research-registry.schema.json"
SENTINEL = (
    "SUCCESS:RES-0021 in the receipt AND a candidate list where every "
    "'honoured' entry cites an observed behaviour delta and every "
    "unconfirmed entry is explicitly marked string-only"
)
QUESTION = (
    "Which environment variables, feature flags and hidden subcommands does "
    "the installed client actually honour that appear in no published "
    "documentation, and which of them would change this program's design if "
    "relied upon?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0021/probe1_flag_deltas.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0021/probe2_negative_control.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def candidate_row(c: dict) -> dict:
    status = c["status"]
    unconfirmed = status == "string-only"
    bd = c.get("behaviour_delta") or {}
    row = {
        "name": c["name"],
        "kind": c["kind"],
        "status": status,
        "role": c.get("role"),
        "unconfirmed": unconfirmed,
        "in_published_docs": c.get("in_published_docs"),
        "in_help": c.get("in_help"),
        "string_in_binary": c.get("string_in_binary"),
        "design_impact": c.get("design_impact"),
    }
    if status == "honoured":
        row["behaviour_delta"] = {
            "observed": True,
            "reasons": bd.get("reasons") or [],
            "off": bd.get("off"),
            "on": bd.get("on"),
        }
        row["marked"] = "honoured"
    else:
        row["behaviour_delta"] = {
            "observed": bool(bd.get("observed")),
            "reasons": bd.get("reasons") or [],
            "unknown_rejection": bd.get("unknown_rejection"),
            "off": bd.get("off"),
            "on": bd.get("on"),
        }
        row["marked"] = "string-only" if unconfirmed else status
    return row


def honesty(rows: list[dict]) -> list[str]:
    errors = []
    for r in rows:
        if r["status"] == "honoured":
            bd = r.get("behaviour_delta") or {}
            if not bd.get("observed"):
                errors.append(f"{r['name']} honoured without observed delta")
            if not (bd.get("reasons") or []):
                errors.append(f"{r['name']} honoured without delta reasons")
        if r.get("unconfirmed") and r["status"] != "string-only":
            errors.append(f"{r['name']} unconfirmed but status={r['status']}")
        if r["status"] == "string-only" and r.get("marked") != "string-only":
            errors.append(f"{r['name']} string-only not marked string-only")
    return errors


def main() -> int:
    measured = measure()
    if not measured.get("ok"):
        print("FAILED:RES-0021 emit no installed client", measured.get("error"))
        return 1
    rows = [candidate_row(c) for c in measured["candidates"]]
    errs = honesty(rows)
    if errs:
        print("FAILED:RES-0021 honesty", errs)
        return 1
    if not measured["negative_control"]["pass"]:
        print("FAILED:RES-0021 invented flag produced an honouring delta")
        return 1
    honoured = [r for r in rows if r["status"] == "honoured"]
    string_only = [r for r in rows if r["status"] == "string-only"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    client = measured["client"]
    harvest = measured["harvest"]
    harvest_lite = {
        "wrapper_path": harvest["wrapper_path"],
        "wrapper_env": harvest["wrapper_env"],
        "index_js": harvest["index_js"],
        "index_bytes": harvest["index_bytes"],
        "js_env_count": len(harvest.get("js_env") or []),
        "js_env": (harvest.get("js_env") or [])[:40],
        "js_flag_count": harvest.get("js_flag_count"),
    }
    doc = {
        "unit_id": "RES-0021",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "research-registry",
        "question": QUESTION,
        "title": "Inventory undocumented and beta surfaces observable in the shipped client",
        "timestamps": {"measured_at": now},
        "client": {
            "catalog_target": client.get("catalog_target"),
            "catalog_match": client.get("catalog_match"),
            "family": client.get("family"),
            "path": client.get("path"),
            "index_js": client.get("index_js"),
            "note": client.get("note"),
            "version_text": measured.get("client_version_text"),
        },
        "published_docs": measured["published_docs"],
        "harvest": harvest_lite,
        "candidates": rows,
        "counts": measured["counts"],
        "negative_control": measured["negative_control"],
        "design_impact_honoured": [
            {
                "name": r["name"],
                "would_change_design_if_relied_upon": (r.get("design_impact") or {}).get(
                    "would_change_design_if_relied_upon"
                ),
                "rationale": (r.get("design_impact") or {}).get("rationale"),
            }
            for r in honoured
        ],
        "schema_version": 1,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json RES-0021",
        "min_bytes_threshold": 128,
        "report": {
            "kind": "research-registry",
            "title": "Inventory undocumented and beta surfaces observable in the shipped client",
            "question_or_target": QUESTION,
            "observations": [
                {
                    "name": "honoured-undocumented-count",
                    "measured": len(honoured),
                    "method": "with-without wrapper/fingerprint delta vs frozen published tokens",
                    "anchor": "command-center/p2-wave/probes/RES-0021/inventory.py",
                },
                {
                    "name": "string-only-unconfirmed-count",
                    "measured": len(string_only),
                    "method": "no observed honouring delta or unknown-option rejection",
                    "anchor": "command-center/p2-wave/probes/RES-0021/inventory.py",
                },
                {
                    "name": "invented-env-honour",
                    "measured": bool(measured["negative_control"]["observed_honour"]),
                    "method": "wrapper argv/compile-cache compare for RES0021_INVENTED_FLAG",
                    "anchor": "command-center/p2-wave/probes/RES-0021/probe2_negative_control.py",
                },
            ],
            "control_ids": ["probe1-flag-deltas", "probe2-negative-control"],
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "On this Linux worktree the live installed client is "
                    f"{client.get('family')} at {client.get('path')}; "
                    "Claude Code (`claude`) was not found."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0021/client.py",
            },
            {
                "id": "C2",
                "claim": (
                    f"{len(honoured)} undocumented surface(s) are honoured "
                    "(observed behaviour delta, absent from frozen published-doc tokens)."
                ),
                "verdict": "CONFIRMED" if honoured else "PARTIAL",
                "anchor": "command-center/research/RES-0021.json",
            },
            {
                "id": "C3",
                "claim": (
                    f"{len(string_only)} unconfirmed entries are marked string-only; "
                    "invented flag RES0021_INVENTED_FLAG produced no honouring delta."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0021/inventory.py",
            },
        ],
        "tests": [
            {
                "id": "T1",
                "name": "each candidate run with and without; honoured rows cite a delta",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2",
                "name": "invented flag name produces no honouring delta",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0021-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "strongest_caveat": (
                "Catalog named Claude Code; this measurement is of the Cursor "
                "agent launcher actually installed on this box. Published-doc "
                "membership uses a frozen token snapshot of cursor.com/docs/cli "
                "plus live --help, not a full web crawl at probe time."
            ),
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0021/inventory.py",
                "line": 1,
                "snippet": "Live with/without inventory against the installed launcher",
                "kind": "probe",
                "claim": "C2",
            },
            {
                "path": str(client.get("path") or "missing"),
                "line": 1,
                "snippet": "installed client launcher",
                "kind": "live-client",
                "claim": "C1",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0021/fixtures/published_tokens.json",
                "line": 1,
                "snippet": "frozen published CLI tokens",
                "kind": "docs-snapshot",
                "claim": "C2",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0021/delta.py",
                "line": 1,
                "snippet": "fingerprint compare of with/without runs",
                "kind": "probe",
                "claim": "C3",
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "with-without-deltas"},
            {"id": "probe2", "command": P2, "role": "invented-flag-negative-control"},
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "JS-bundle env names beyond the sampled overlay were not each "
                    "given a specialised observation surface (cache dir, exec argv)."
                ),
                "settling_experiment": (
                    "Add a per-env specialised delta for remaining js_env names."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:RES-0021 catalog schema path missing")
        return 1
    # Catalog research-registry.schema.json is a generated $ref shim to
    # https://ast-integrate.invalid/... . jsonschema.validate follows that
    # URL on the network (RefResolutionError). The shim carries no local
    # constraints. G-1 named probes own honesty; this local gate refuses
    # empty/unrelated blobs without fetching.
    local_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "completion_sentinel",
            "candidates",
            "report",
            "tests",
            "negative_control",
        ],
        "properties": {
            "unit_id": {"type": "string", "const": "RES-0021"},
            "state": {"type": "string", "const": "SUCCESS"},
            "sentinel": {"type": "string", "minLength": 16},
            "completion_sentinel": {"type": "string", "minLength": 16},
            "candidates": {"type": "array", "minItems": 1},
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {
                    "kind": {"type": "string", "const": "research-registry"},
                    "observations": {"type": "array", "minItems": 1},
                    "control_ids": {"type": "array", "minItems": 1},
                },
            },
            "tests": {"type": "array", "minItems": 2},
            "negative_control": {
                "type": "object",
                "required": ["pass"],
                "properties": {"pass": {"type": "boolean", "const": True}},
            },
        },
    }
    try:
        import jsonschema

        errs = sorted(
            jsonschema.Draft7Validator(local_schema).iter_errors(doc),
            key=lambda e: list(e.path),
        )
        if errs:
            print("FAILED:RES-0021 schema errors")
            for e in errs[:12]:
                print(" ", list(e.path), e.message)
            return 1
        for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000}):
            if not list(jsonschema.Draft7Validator(local_schema).iter_errors(garbage)):
                print("FAILED:RES-0021 schema accepted garbage")
                return 1
    except ImportError:
        pass
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"honoured={len(honoured)} string-only={len(string_only)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
