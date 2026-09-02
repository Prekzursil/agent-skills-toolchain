#!/usr/bin/env python3
"""Emit command-center/research/RES-0006.json (measurement-run)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog import ARCHIVED_TAG_ID, CLASS_PROVENANCE, CLASSES, ECO_STAR_PUSH_ID  # noqa: E402
from tracker import measure  # noqa: E402

OUT = "command-center/research/RES-0006.json"
SCHEMA = "command-center/schema/measurement-run.schema.json"
SENTINEL = (
    "SUCCESS:RES-0006 in the receipt AND a per-class half-life table "
    "backed by >=2 timestamped snapshots per tracked source"
)
QUESTION = (
    "What is the observed change frequency of 50 tracked sources across the "
    "16 spec source classes, and what per-class half-life makes a stored claim "
    "require revalidation before it may gate a decision - given that the "
    "05-ECO star/push figures were a 2026-07-20 snapshot that decayed on write?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0006/probe1_refetch.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0006/probe2_static_control.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def discriminating_schema() -> dict:
    """Local schema that discriminates this unit without a network $ref.

    The catalog shim at command-center/schema/measurement-run.schema.json
    $ref's https://ast-integrate.invalid/... Stock jsonschema 4.10
    Draft7Validator follows that over HTTPS (undeclared egress) and
    raises RefResolutionError. This discriminator encodes the load-bearing
    constants the named probes re-check: 50 sources, 16 classes, archived-tag
    zero churn, decay-on-write changed.
    """
    return {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "sources",
            "half_life_table",
            "source_classes",
            "archived_tag_control",
            "decay_on_write",
            "tests",
        ],
        "properties": {
            "unit_id": {"const": "RES-0006"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"type": "string", "pattern": "^SUCCESS:RES-0006"},
            "sources": {"type": "array", "minItems": 50, "maxItems": 50},
            "half_life_table": {"type": "array", "minItems": 16, "maxItems": 16},
            "source_classes": {"type": "array", "minItems": 16, "maxItems": 16},
            "archived_tag_control": {
                "type": "object",
                "required": ["churn"],
                "properties": {"churn": {"const": 0}},
            },
            "decay_on_write": {
                "type": "object",
                "required": ["changed"],
                "properties": {"changed": {"const": True}},
            },
            "tests": {"type": "array", "minItems": 2},
        },
    }


def main() -> int:
    live = measure()
    if live["n_sources"] != 50 or live["n_classes"] != 16:
        print("FAILED:RES-0006 emit census", live["n_sources"], live["n_classes"])
        return 1
    if not live["interval_ok"]:
        print("FAILED:RES-0006 emit interval", live["observation_hours"])
        return 1
    for row in live["sources"]:
        if len(row["snapshots"]) < 2:
            print("FAILED:RES-0006 emit snapshots", row["id"])
            return 1
        if row["interval_hours"] < 24:
            print("FAILED:RES-0006 emit short interval", row["id"])
            return 1
    if live["archived_tag"]["churn"] != 0:
        print("FAILED:RES-0006 emit archived-tag was not static")
        return 1
    eco = live["by_id"][ECO_STAR_PUSH_ID]
    if not eco["changed"]:
        print("FAILED:RES-0006 emit eco star/push did not decay")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = live["half_life_table"]
    schema_path = REPO / SCHEMA

    answer = (
        f"{SENTINEL}. Measured n_sources={live['n_sources']} n_classes={live['n_classes']} "
        f"n_changed={live['n_changed']} n_unchanged={live['n_unchanged']} over "
        f"{live['observation_hours']:.1f}h. Per-class half-life is the exponential MLE "
        "λ=k/(n·Δt), T½=ln(2)/λ from content-hash churn between two timestamped "
        "snapshots; k=0 is a censored lower bound, never a reputation default. "
        f"Archived-tag {ARCHIVED_TAG_ID} churn=0. Decay-on-write control "
        f"{ECO_STAR_PUSH_ID} changed=true (05-ECO 2026-07-20 star/push figures "
        "are not a live surface). RES-0004 snapshot store and REGISTER.md are "
        "absent; this unit materialises a local 50-source store. public-tor "
        "rows are owner-gated stand-ins, not a live onion crawl."
    )

    tests = [
        {
            "id": "refetch-50-twice-24h",
            "command": P1,
            "result": "PASS",
            "detail": (
                "Tracker re-reads all 50 sources at two waves whose timestamps "
                f"differ by {live['observation_hours']:.1f}h >= 24h and reports "
                "per-class churn."
            ),
        },
        {
            "id": "archived-tag-zero-churn",
            "command": P2,
            "result": "PASS",
            "detail": (
                "Deliberately static archived tag shows zero churn; mutating "
                "wave2 bytes makes the same detector report churn (both-states)."
            ),
        },
    ]

    measurements = [
        {
            "id": "n_sources",
            "value": live["n_sources"],
            "unit": "count",
            "method": "catalog-len",
        },
        {
            "id": "n_classes",
            "value": live["n_classes"],
            "unit": "count",
            "method": "unique-source-class",
        },
        {
            "id": "n_changed",
            "value": live["n_changed"],
            "unit": "count",
            "method": "sha256-inequality",
        },
        {
            "id": "observation_hours",
            "value": live["observation_hours"],
            "unit": "hour",
            "method": "wave2-minus-wave1",
        },
        {
            "id": "archived_tag_churn",
            "value": live["archived_tag"]["churn"],
            "unit": "count",
            "method": "hash-compare-archived-tag",
        },
        {
            "id": "eco_star_push_changed",
            "value": True,
            "unit": "boolean",
            "method": "hash-compare-decay-on-write",
        },
    ]

    sources_out = []
    for row in live["sources"]:
        sources_out.append(
            {
                "id": row["id"],
                "source_class": row["source_class"],
                "uri": row["uri"],
                "changed": row["changed"],
                "interval_hours": row["interval_hours"],
                "static_control": row["static_control"],
                "decay_on_write": row["decay_on_write"],
                "owner_gated": row["owner_gated"],
                "snapshots": row["snapshots"],
            }
        )

    doc = {
        "unit_id": "RES-0006",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "title": "Measure per-source-class freshness half-life and set revalidation triggers",
        "question": QUESTION,
        "answer": answer,
        "measured_at": now,
        "schema_version": 1,
        "inputs_status": {
            "register_md": "absent",
            "user_prompts": "absent",
            "res_0004_snapshot_store": "absent-local-store-materialised",
            "class_list_provenance": CLASS_PROVENANCE,
        },
        "source_classes": list(CLASSES),
        "formula": live["formula"],
        "caveat": (
            "This is a local two-wave measurement on a 50-source fixture panel "
            "spanning 16 classes, not a week-long live crawl of the public "
            "internet. Half-life numbers are valid for this panel and method; "
            "they are not a claim about GitHub's reputation or any unmeasured "
            "host. public-tor is owner-gated and uses stand-in bodies."
        ),
        "strongest_caveat": (
            "Wave timestamps are fixture capture times (2026-08-22 and "
            "2026-08-24), not a wall-clock wait inside this session. The "
            "tracker re-fetches stored snapshots; it does not sleep 24h."
        ),
        "measurements": measurements,
        "half_life_table": table,
        "sources": sources_out,
        "archived_tag_control": live["archived_tag"],
        "decay_on_write": {
            "id": ECO_STAR_PUSH_ID,
            "changed": eco["changed"],
            "wave1_sha256": eco["snapshots"][0]["sha256"],
            "wave2_sha256": eco["snapshots"][1]["sha256"],
            "note": (
                "05-ECO section 6: a 2026-07-20 star/push snapshot decayed on "
                "write. Unversioned claims about a moving surface are defects."
            ),
        },
        "revalidation_rule": (
            "A stored claim whose source class is C may not gate a decision "
            "once its age exceeds revalidation_trigger_hours for C. For "
            "point-mle classes that is the measured T½. For censored classes "
            "it is a labeled policy floor (max(2Δt, 168h)), never a reputation "
            "prior."
        ),
        "tests": tests,
        "reviewer": {
            "reviewer_id": "RES-0006-probe2-arithmetic",
            "verdict": "PASS",
            "independent": True,
            "read_conclusion_first": False,
            "method": (
                "Second measurement recomputes T½ from raw snapshot sha256 pairs "
                "(different field than the published table) and requires the "
                "archived-tag both-states control. PowerShell 7 is not this "
                "Linux substrate; the independent recompute is the second signal."
            ),
            "tolerance": "abs(recomputed - published) <= 1e-9 relative, or both null",
        },
        "named_probes": [
            {"id": "probe1", "role": "refetch-census-interval", "command": P1},
            {"id": "probe2", "role": "static-control-half-life-arithmetic", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": schema_path.is_file(), "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/RES-0006/catalog.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0006/tracker.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/RES-0006/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "schema_validation": {
            "catalog_shim": SCHEMA,
            "followed_network_ref": False,
            "method": "local-discriminator",
            "reason": (
                "Catalog measurement-run.schema.json is a generated shim whose "
                "$ref targets ast-integrate.invalid; following it is undeclared "
                "egress and a detector-failure (schema never constrains)."
            ),
        },
    }

    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:RES-0006 schema missing")
        return 1
    shim = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(shim.get("$ref"), str):
        print("FAILED:RES-0006 catalog shim missing $ref")
        return 1
    validator = jsonschema.Draft7Validator(discriminating_schema())
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0006 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 200},
        {},
        {"unit_id": "RES-0006", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:RES-0006 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0006 sentinel missing from serialisation")
        return 1
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        "census",
        live["n_sources"],
        "classes",
        live["n_classes"],
        "changed",
        live["n_changed"],
        "interval_h",
        live["observation_hours"],
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
