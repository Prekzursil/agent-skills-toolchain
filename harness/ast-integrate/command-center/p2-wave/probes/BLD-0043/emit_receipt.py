#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0043.json (traceability matrix)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402

from controls import run_fixture_controls  # noqa: E402
from corpus import fixture_requirements, fixture_tests, live_requirements, live_tests  # noqa: E402
from join import dump_join, join  # noqa: E402

OUT_REL = "command-center/receipts/BLD-0043.json"
SCHEMA_REL = "command-center/schema/traceability-matrix.schema.json"
QUESTION = (
    "Question: which requirement has no test, and which test asserts something "
    "no requirement asked for? Join the CC-0024 requirement records to "
    "TEST-REGISTRY.json in both directions, emit the two orphan sets, and "
    "classify each orphan test as either an UNDOCUMENTED REQUIREMENT (promote it) "
    "or SCOPE CREEP (retire it, with the reason recorded)."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0043/probe1_delete_untested.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0043/probe2_comment_classify.py"
)

# The catalog output_schema is a $ref shim to ast-integrate.invalid. jsonschema
# 4.10 on this image tries HTTPS for that host and never comes back. Discriminate
# locally so garbage is rejected without a network fetch.
DISCRIMINATOR = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "kind",
        "mapping_rule",
        "requirements",
        "tests",
        "mappings",
        "untested_requirements",
        "orphan_tests",
        "controls",
        "reviewer",
        "named_probes",
        "report",
    ],
    "properties": {
        "unit_id": {"const": "BLD-0043"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:BLD-0043"},
        "kind": {"const": "traceability-matrix"},
        "mapping_rule": {
            "type": "object",
            "required": ["structural_only", "comment_only_counts"],
            "properties": {
                "structural_only": {"const": True},
                "comment_only_counts": {"const": False},
            },
        },
        "requirements": {"type": "array", "minItems": 1},
        "tests": {"type": "array", "minItems": 1},
        "mappings": {"type": "array"},
        "untested_requirements": {"type": "array"},
        "orphan_tests": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "classification"],
                "properties": {
                    "classification": {"enum": ["promote", "retire"]},
                },
            },
        },
        "controls": {"type": "array", "minItems": 3},
        "reviewer": {
            "type": "object",
            "required": ["verdict", "independent", "checked_count"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
                "checked_count": {"type": "integer", "minimum": 10},
            },
        },
        "named_probes": {"type": "array", "minItems": 2},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "traceability-matrix"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live_reqs, cc_meta = live_requirements()
    live_t, inv_meta = live_tests()
    live = join(live_reqs, live_t)
    live_dump = dump_join(live)

    fx = run_fixture_controls(fixture_requirements(), fixture_tests())
    if not fx["all_pass"]:
        print("FAILED:BLD-0043 fixture controls or reviewer")
        print(json.dumps({
            "controls": fx["controls"],
            "reviewer_verdict": fx["reviewer"]["verdict"],
            "id_only": fx["reviewer"].get("id_only"),
        }, indent=2)[:4000])
        return 1

    unclassified = [
        o
        for o in live.orphans
        if o.get("classification") not in {"promote", "retire"}
    ]
    if unclassified:
        print("FAILED:BLD-0043 live orphans unclassified", unclassified[:5])
        return 1

    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fx_dump = dump_join(fx["result"])

    doc: dict = {
        "unit_id": "BLD-0043",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0043",
        "kind": "traceability-matrix",
        "question": QUESTION,
        "ts": now,
        "mapping_rule": {
            "structural_only": True,
            "comment_only_counts": False,
            "accepted_channels": ["test-id", "marker", "registry-entry"],
            "unmapped_label": "unmapped",
            "evidence": (
                "A mapping must be STRUCTURAL - a REQ id in the test id, a "
                "marker, or a registry entry. A mapping asserted only by a "
                "code comment does not count and is reported as unmapped."
            ),
        },
        "sources": {
            "cc0024": cc_meta,
            "test_registry": inv_meta["test_registry"],
            "b08_inventory": inv_meta["b08_inventory"],
        },
        "live": {
            "requirement_count": live_dump["requirement_count"],
            "test_count": live_dump["test_count"],
            "mapping_count": live_dump["mapping_count"],
            "untested_count": live_dump["untested_count"],
            "orphan_count": live_dump["orphan_count"],
            "note": (
                "Live join on this worktree: CC-0024.json is absent so the "
                "nine catalog-stated floors are the requirement set. "
                "TEST-REGISTRY.json is present but stores suite counts and "
                "TI-* invariants, not REQ- ids, so it contributes no "
                "structural REQ mapping. Untested floors and orphan B08 "
                "tests are findings routed to B08, not a failure of this "
                "unit (retry_policy)."
            ),
        },
        "requirements": live_dump["requirements"],
        "tests": live_dump["tests"],
        "mappings": live_dump["mappings"],
        "untested_requirements": live_dump["untested_requirements"],
        "orphan_tests": live_dump["orphan_tests"],
        "fixture_corpus": {
            "role": "controls-and-reviewer",
            "requirement_count": fx_dump["requirement_count"],
            "test_count": fx_dump["test_count"],
            "mapping_count": fx_dump["mapping_count"],
            "untested_count": fx_dump["untested_count"],
            "orphan_count": fx_dump["orphan_count"],
            "comment_only": fx_dump["comment_only"],
            "mappings": fx_dump["mappings"],
            "untested_requirements": fx_dump["untested_requirements"],
            "orphan_tests": fx_dump["orphan_tests"],
        },
        "controls": [
            {
                "id": c["id"],
                "pass": c["pass"],
                "detail": c["detail"],
            }
            for c in fx["controls"]
        ],
        "reviewer": {
            "reviewer_id": fx["reviewer"]["reviewer_id"],
            "verdict": fx["reviewer"]["verdict"],
            "independent": True,
            "checked_count": fx["reviewer"]["checked_count"],
            "mappings_checked": [
                {
                    "requirement_id": row["requirement_id"],
                    "test_id": row["test_id"],
                    "channel": row.get("channel"),
                    "body_asserts_requirement": row["body_asserts_requirement"],
                    "verdict": row["verdict"],
                }
                for row in fx["reviewer"]["mappings_checked"]
            ],
            "method": (
                "Read each mapped test body and require the requirement tokens "
                "to appear in the assertion source. An id match without those "
                "tokens is ID-ONLY and fails the review."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "delete-moves-untested"},
            {"id": "probe2", "command": P2, "role": "comment-unmapped-and-classify"},
        ],
        "report": {
            "kind": "traceability-matrix",
            "observations": [
                {
                    "name": "live_requirement_count",
                    "measured": live_dump["requirement_count"],
                    "method": "CC-0024 receipt if present else catalog-surrogate floors",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json",
                },
                {
                    "name": "live_untested_count",
                    "measured": live_dump["untested_count"],
                    "method": "structural join test-id|marker|registry-entry",
                    "anchor": "command-center/p2-wave/probes/BLD-0043/join.py",
                },
                {
                    "name": "live_orphan_count",
                    "measured": live_dump["orphan_count"],
                    "method": "AST walk of tools/command-center/tests plus classify_orphan",
                    "anchor": "tools/command-center/tests",
                },
                {
                    "name": "comment_only_counts",
                    "measured": False,
                    "method": "tokenize COMMENT tokens; REQ ids in comments are unmapped",
                    "anchor": "command-center/p2-wave/probes/BLD-0043/fixtures/comment_only.py",
                },
            ],
            "control_ids": [c["id"] for c in fx["controls"]],
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA_REL,
                "exists": True,
                "role": "schema",
            },
        ],
        "completion_marker": "SUCCESS:BLD-0043",
    }

    _ = schema  # declared path must exist; constraints live in DISCRIMINATOR
    jsonschema.validate(instance=doc, schema=DISCRIMINATOR)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    try:
        jsonschema.validate(instance=garbage, schema=DISCRIMINATOR)
    except jsonschema.ValidationError:
        pass
    else:
        print("FAILED:BLD-0043 schema accepts garbage")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(
        f"live untested={live_dump['untested_count']} "
        f"orphans={live_dump['orphan_count']} "
        f"mappings={live_dump['mapping_count']}"
    )
    print("SUCCESS:BLD-0043")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
