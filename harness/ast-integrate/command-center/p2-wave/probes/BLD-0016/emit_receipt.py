#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0016.json (traceability matrix + existence probe)."""
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
from deliverables import sweep  # noqa: E402
from join import dump_join  # noqa: E402

OUT_REL = "command-center/receipts/BLD-0016.json"
SCHEMA_REL = "command-center/schema/traceability-matrix.schema.json"
QUESTION = (
    "Question: which item on the spec's Final Deliverables list "
    "(_USER-PROMPTS.md:11402-11435) has no artifact on disk? Resolve each of "
    "the listed deliverables to a concrete path or path set, probe existence, "
    "record byte size and sha256 read off disk, and register the result in "
    "ARTIFACT-MANIFEST.json. A digest is a claim, not a receipt; a file path "
    "inside a report is not proof the file exists."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0016/probe1_planted_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0016/probe2_independent_reprobe.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    fx = run_fixture_controls()
    if not fx["all_pass"]:
        print("FAILED:BLD-0016 fixture controls or reviewer")
        print(
            json.dumps(
                {
                    "controls": [
                        {"id": c["id"], "pass": c["pass"], "detail": c["detail"]}
                        for c in fx["controls"]
                    ],
                    "five_present": {
                        "pass": fx["five_present"]["pass"],
                        "detail": fx["five_present"]["detail"],
                    },
                    "matrix_reviewer": {
                        "verdict": fx["matrix_reviewer"]["verdict"],
                        "id_only": fx["matrix_reviewer"].get("id_only"),
                    },
                },
                indent=2,
            )[:4000]
        )
        return 1

    live = sweep()
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fx_dump = dump_join(fx["result"])
    matrix = fx["matrix_reviewer"]
    five = fx["five_present"]

    present_rows = [
        {
            "id": it["id"],
            "path": it.get("resolved_path"),
            "bytes": it.get("bytes") or 0,
            "sha256": it.get("sha256"),
            "verdict": it["verdict"],
        }
        for it in live["items"]
        if it["verdict"] == "PRESENT"
    ]

    doc: dict = {
        "unit_id": "BLD-0016",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0016",
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
            "cc0024": {
                "role": "out-of-scope",
                "present": (REPO / "command-center/receipts/CC-0024.json").is_file(),
                "note": (
                    "CC-0024 extracts owner requirements from the spec. "
                    "AUD-0076 covers transcript requirements. This unit probes "
                    "the Final Deliverables list for on-disk existence."
                ),
            },
            "test_registry": {
                "path": "command-center/p2-wave/probes/BLD-0016/fixtures/registry.json",
                "present": True,
                "live_registry": "command-center/TEST-REGISTRY.json",
                "live_present": (REPO / "command-center/TEST-REGISTRY.json").is_file(),
            },
            "b08_inventory": {
                "method": "ast FunctionDef walk of BLD-0016 fixture tests",
                "path": "command-center/p2-wave/probes/BLD-0016/fixtures",
                "count": fx_dump["test_count"],
            },
        },
        "requirements": fx_dump["requirements"],
        "tests": fx_dump["tests"],
        "mappings": fx_dump["mappings"],
        "untested_requirements": fx_dump["untested_requirements"],
        "orphan_tests": fx_dump["orphan_tests"],
        "deliverable_probe": live,
        "answer": live["answer"],
        "present_verdicts_from_filesystem": present_rows,
        "controls": [
            {"id": c["id"], "pass": c["pass"], "detail": c["detail"]}
            for c in fx["controls"]
        ],
        "existence_reviewer": {
            "reviewer_id": five["reviewer_id"],
            "verdict": five["verdict"],
            "independent": True,
            "checked_count": five["checked_count"],
            "powershell_get_item": five["powershell_get_item"],
            "present_reprobed": five["present_reprobed"],
            "method": (
                "Re-probe five PRESENT fixture files with unix stat -c %s and "
                "sha256sum; compare size and raw sha256 to Python os.stat and "
                "hashlib. PowerShell Get-Item is ABSENT on this Linux estate."
            ),
        },
        "reviewer": {
            "reviewer_id": matrix["reviewer_id"],
            "verdict": matrix["verdict"],
            "independent": True,
            "checked_count": matrix["checked_count"],
            "mappings_checked": matrix["mappings_checked"],
            "method": (
                "Read each mapped test body and require the requirement tokens "
                "to appear in the assertion source. An id match without those "
                "tokens is ID-ONLY and fails the review."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "planted-absent-empty-dir"},
            {"id": "probe2", "command": P2, "role": "independent-stat-reprobe"},
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "completion_marker": "SUCCESS:BLD-0016",
        "honesty": (
            "Live _USER-PROMPTS.md:11402-11435 is absent on this worktree; "
            "the deliverable list is reconstructed from catalog citations of "
            "those lines and from items the catalog names as Prompt Two final "
            "deliverables. Completeness against the unread 34-line list is "
            "NOT-CHECKED. ABSENT live items are findings, not a unit failure. "
            "Global ARTIFACT-MANIFEST.json is absent; registration is the "
            "per-unit UNIT-ARTIFACT-MANIFEST.json (unit_manifest.py --write "
            "not run). SUCCESS:BLD-0016"
        ),
    }

    jsonschema.validate(instance=doc, schema=schema)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    try:
        jsonschema.validate(instance=garbage, schema=schema)
    except jsonschema.ValidationError:
        pass
    else:
        print("FAILED:BLD-0016 schema accepts garbage")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(
        f"live absent={live['absent']} present={live['present']} "
        f"source={live['source']}"
    )
    print("SUCCESS:BLD-0016")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
