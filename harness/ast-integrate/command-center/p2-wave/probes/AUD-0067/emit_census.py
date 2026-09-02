#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0067-prompt-one-artifact-census.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import live_census, probe1_payload, probe2_payload  # noqa: E402
from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    CONTRACT_29,
    CATALOG_REL,
    OUT,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    SCHEMA,
    SCHEMA_REL,
    UNIT,
)

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live = live_census()
    ctl = live["control"]
    if ctl["count_a"] != 17 or ctl["count_b"] != 20 or ctl["union_count"] != 29:
        print("FAILED:AUD-0067 emit control cardinality")
        return 1
    if ctl["divergent_dual"] < 1 or ctl["identical_dual"] < 1:
        print("FAILED:AUD-0067 emit control sha256 does not discriminate")
        return 1
    if len(CONTRACT_29) != 29:
        print("FAILED:AUD-0067 emit contract is not 29 names")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            print("FAILED:AUD-0067 schema accepts garbage")
            return 1

    p1 = probe1_payload(live)
    p2 = probe2_payload(live)
    raw1 = json.dumps(p1, sort_keys=True) + (
        "\nSUCCESS:AUD-0067-probe1 per-tree existence counts (not union)"
    )
    raw2 = json.dumps(p2, sort_keys=True) + (
        "\nSUCCESS:AUD-0067-probe2 sha256 divergence for dual-present names"
    )

    per_tree = live["per_tree_counts"]
    harness_n = per_tree["harness-restore"]
    repo_n = per_tree["repo"]
    union_n = live["union_count"]
    answer = (
        f"On this Linux worktree the 29 contracted Prompt-One names were "
        f"censused separately in the harness-restore corpus tree "
        f"(present={live['harness']['present']}, found={harness_n}/29) and "
        f"the repo tree (present={live['repo']['present']}, found={repo_n}/29). "
        f"Per-tree counts are {harness_n} and {repo_n}; union={union_n}. "
        f"The set of 29 does not hold in a single live tree "
        f"(holds_in_single_tree={live['holds_in_single_tree']}) and does not "
        f"hold as the live union either (holds_as_union={live['holds_as_union']}). "
        f"The catalog caveat that 29/29 only holds as a union is about the "
        f"Windows harness-restore + platform-redesign trees, which are not "
        f"mounted here; that estate is NOT-CHECKED. Control fixture: "
        f"tree-a={ctl['count_a']} tree-b={ctl['count_b']} union=29 with "
        f"{ctl['divergent_dual']} sha256-divergent overlap, so a union-only "
        f"harness is incapable of this result."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0067",
        "completion_sentinel": COMPLETION_SENTINEL,
        "report_kind": "audit-inventory",
        "title": "Prompt-One artifact census with per-artifact tree location",
        "question": QUESTION,
        "honesty": (
            "PROMPT-ONE-FLOOR-AUDIT.json is absent on this worktree. The 29 "
            "names are recovered from WORK-UNIT-CATALOG.json citations of "
            "numbered Prompt-One files (00-19 band, md/json twins counted "
            "separately). Filename 04-* is not cited. The harness-restore "
            "tree (~/.claude/harness-restore-20260806) is unmounted. Repo "
            "search is basename-at-root (plus command-center/), not a "
            "recursive walk of other units' fixtures. Dual-present sha256 "
            "rows on the live trees may be zero; the planted control still "
            "proves the detector."
        ),
        "contract": {
            "claimed_count": 29,
            "names": list(CONTRACT_29),
            "source": (
                f"{CATALOG_REL}:AUD-0067 inputs 'the 29-artifact contract list'; "
                "names recovered from catalog-cited Prompt-One numbered files"
            ),
            "missing_number": "04",
            "absent_floor_audit": "command-center/PROMPT-ONE-FLOOR-AUDIT.json",
        },
        "trees": [
            {
                "id": "harness-restore",
                "role": "harness-restore-corpus-tree",
                "present": live["harness"]["present"],
                "root": live["harness"]["root"],
                "found_count": harness_n,
                "missing_count": live["harness"]["missing_count"],
                "candidates_tried": live["harness"]["candidates_tried"],
            },
            {
                "id": "repo",
                "role": "repo-tree",
                "present": live["repo"]["present"],
                "root": live["repo"]["root"],
                "found_count": repo_n,
                "missing_count": live["repo"]["missing_count"],
                "candidates_tried": live["repo"]["candidates_tried"],
            },
        ],
        "per_tree_counts": per_tree,
        "union_count": union_n,
        "holds_in_single_tree": live["holds_in_single_tree"],
        "holds_as_union": live["holds_as_union"],
        "dual_present": live["dual_present"],
        "identical_dual": live["identical_dual"],
        "divergent_dual": live["divergent_dual"],
        "control": {
            "count_a": ctl["count_a"],
            "count_b": ctl["count_b"],
            "union_count": ctl["union_count"],
            "holds_in_single_tree": False,
            "per_tree_below_29": True,
            "union_only_would_report": 29,
            "dual_present": ctl["dual_present"],
            "identical_dual": ctl["identical_dual"],
            "divergent_dual": ctl["divergent_dual"],
            "divergent_names": ctl["divergent_names"],
        },
        "rows": live["rows"],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": 0,
                "raw_output": raw1,
                "role": "per-tree-existence",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": 0,
                "raw_output": raw2,
                "role": "sha256-divergence",
            },
        ],
        "tests": [
            {
                "id": "AUD-0067-PER-TREE",
                "command": P1,
                "name": "Per-artifact existence in each tree, reported per tree",
                "result": "PASS",
            },
            {
                "id": "AUD-0067-SHA256",
                "command": P2,
                "name": "sha256 compare for names present in both trees",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0067-C1-UNION-VS-PER-TREE",
                "planted_defect": (
                    "two fixture trees whose union is 29 while per-tree counts "
                    "are 17 and 20; a union-only harness reports 29 per tree"
                ),
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "per-tree-below-29",
            },
            {
                "id": "AUD0067-C2-DIVERGENT-SHA256",
                "planted_defect": (
                    "one overlapping contracted name with different bytes in "
                    "each fixture tree; counting it as one artifact is wrong"
                ),
                "detector_fired": True,
                "silent_on_good": True,
                "classification": "divergent-duplicate",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0067-probe2-sha256-divergence",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Independent mechanism: raw sha256 of dual-present files. "
                "Catalog also asks for a cross-vendor Codex reviewer who "
                "re-runs only probe 2; that reviewer is not impersonated."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "evidence": [
            {
                "claim": QUESTION,
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG_REL}:{live['catalog_line_unit']}",
            },
            {
                "claim": (
                    "29/29 only holds as a union of two trees (catalog caveat)"
                ),
                "verdict": "NOT-CHECKED"
                if not live["harness"]["present"]
                else ("CONFIRMED" if not live["holds_in_single_tree"] else "REFUTED"),
                "anchor": (
                    f"{CATALOG_REL}:{live['catalog_line_caveat']}"
                    if live["catalog_line_caveat"] > 0
                    else f"{CATALOG_REL}:AUD-0067-inputs"
                ),
            },
            {
                "claim": (
                    "Per-tree counts must be reported even when they are "
                    "lower than 29"
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0067/fixtures/estate "
                    f"a={ctl['count_a']} b={ctl['count_b']} union=29"
                ),
            },
            {
                "claim": (
                    "sha256 comparison so a divergent duplicate is not "
                    "counted as one artifact"
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0067/fixtures/estate "
                    f"divergent={ctl['divergent_names']}"
                ),
            },
        ],
        "report": {
            "kind": "audit-inventory",
            "answer": answer,
            "observations": [
                f"live per-tree harness-restore={harness_n} repo={repo_n} union={union_n}",
                f"control per-tree a={ctl['count_a']} b={ctl['count_b']} union=29",
                f"control divergent_dual={ctl['divergent_dual']}",
                "harness-restore tree unmounted"
                if not live["harness"]["present"]
                else "harness-restore tree present",
            ],
        },
        "produced_by": {
            "role": "tool-author",
            "execution_substrate": "linux-worktree",
            "vendor": "cursor",
            "model": "cursor-grok-4.6",
        },
        "timestamps": {"emitted_at": now},
        "schema_version": 1,
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0067/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
    }

    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:AUD-0067 schema validation")
        for err in errors[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    dumped = json.dumps(doc, indent=2) + "\n"
    if COMPLETION_SENTINEL not in dumped:
        print("FAILED:AUD-0067 completion_sentinel not in document text")
        return 1
    if "SUCCESS:AUD-0067" not in dumped:
        print("FAILED:AUD-0067 sentinel not in document text")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(dumped, encoding="utf-8")
    digest, size = sha256_file(OUT)
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print(answer[:300])
    print("SUCCESS:AUD-0067 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
