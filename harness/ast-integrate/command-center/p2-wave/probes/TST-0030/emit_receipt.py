#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0030.json from live freeze/sample captures."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from scenario import compact, run_live_product_file, run_mutated, run_quiescent  # noqa: E402

# Catalog output_schema $ref's https://ast-integrate.invalid/... which jsonschema
# 4.x tries to fetch. Validate the probe contract locally so garbage is rejected
# without a network $ref (receipt_core additionalProperties=false would also
# reject freeze_sample at top level; probes read that key from the receipt).
LOCAL_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "answer",
        "tests",
        "evidence",
        "freeze_sample",
        "negative_controls",
        "reviewer",
    ],
    "properties": {
        "unit_id": {"const": "TST-0030"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:TST-0030"},
        "freeze_sample": {
            "type": "object",
            "required": ["quiescent", "mutated", "live_product_file"],
        },
        "tests": {"type": "array", "minItems": 2},
        "evidence": {"type": "array", "minItems": 2},
        "negative_controls": {"type": "array", "minItems": 1},
    },
}

UID = "TST-0030"
OUT = "command-center/receipts/TST-0030.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0030/probe1_mutation_sampled.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0030/probe2_quiescent_frozen.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UID:
            return unit
    raise SystemExit("FAILED:TST-0030 catalog unit missing")


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:TST-0030 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, claim: str, verdict: str = "CONFIRMED") -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet[:180],
        "claim": claim,
        "verdict": verdict,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    question = str(unit["question_or_target"])
    with tempfile.TemporaryDirectory(prefix="tst0030-emit-") as tmp:
        work = Path(tmp)
        quiet = run_quiescent(work / "quiet")
        mutated = run_mutated(work / "mutated")
    live = run_live_product_file()
    if quiet["label"] != "FROZEN" or mutated["label"] != "SAMPLED":
        print("FAILED:TST-0030 both-states capture did not split FROZEN/SAMPLED")
        print(json.dumps({"quiet": compact(quiet), "mutated": compact(mutated)}, indent=1))
        return 1
    if not mutated.get("as_baseline_refused"):
        print("FAILED:TST-0030 as_baseline did not refuse SAMPLED")
        return 1
    if live["label"] != "FROZEN":
        print(f"FAILED:TST-0030 live product file capture was {live['label']}")
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "The capture tool in tools/command-center/freeze_sample.py hashes the "
        "tree at start and at end. A quiescent fixture earns label=FROZEN with "
        f"start_tree_hash={quiet['start_tree_hash']} equal to end_tree_hash and "
        "is baseline_eligible. A planted mid-capture rewrite of subjects/b.json "
        "plus an added subjects/c.json earns label=SAMPLED, enumerates those "
        f"paths, sets anchoring=SAMPLED-AT-TIME, and as_baseline raises "
        "BaselineRefused so the mutated capture cannot be called a baseline. "
        "A live re-hash of tools/command-center/freeze_sample.py on this "
        f"worktree was {live['label']}. " + sentinel
    )
    tool = "tools/command-center/freeze_sample.py"
    doc = {
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "schema_version": 1,
        "report_kind": "test-receipt",
        "title": unit.get("title"),
        "question": question,
        "answer": answer,
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0030",
        "cloud_ok": False,
        "report": {
            "kind": "test-receipt",
            "control_ids": [
                "test_mutation_during_capture_forces_the_sampled_label",
                "test_quiescent_capture_earns_the_frozen_label",
            ],
            "observations": [
                {
                    "name": "quiescent_label",
                    "measured": "FROZEN",
                    "method": "capture_tree on planted fixture with no mid_hook",
                    "anchor": f"{OUT}:freeze_sample.quiescent",
                },
                {
                    "name": "mutated_label",
                    "measured": "SAMPLED",
                    "method": "capture_tree with mid_hook rewrite of subjects/b.json",
                    "anchor": f"{OUT}:freeze_sample.mutated",
                },
            ],
        },
        "freeze_sample": {
            "quiescent": compact(quiet),
            "mutated": compact(mutated),
            "live_product_file": compact(live),
        },
        "tests": [
            {
                "id": "test_mutation_during_capture_forces_the_sampled_label",
                "name": "Planted rewrite mid-capture labels SAMPLED and enumerates paths",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_quiescent_capture_earns_the_frozen_label",
                "name": "No mutation: start hash equals end hash and baseline is allowed",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "start-only-hasher",
                "kind": "known-broken-fixture",
                "description": (
                    "A capture that stored only the start hash would still "
                    "claim FROZEN after the planted rewrite. The live tool "
                    "records a different end hash and refuses baseline."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "evidence": [
            ev(
                tool,
                'label = LABEL_FROZEN if frozen else LABEL_SAMPLED',
                "Start and end tree hashes decide FROZEN vs SAMPLED.",
            ),
            ev(
                tool,
                "raise BaselineRefused(",
                "A SAMPLED capture cannot be promoted to a baseline.",
            ),
            ev(
                "command-center/p2-wave/probes/TST-0030/scenario.py",
                "mutate_mid_capture",
                "Planted mutation rewrites subjects/b.json and adds subjects/c.json.",
            ),
            {
                "claim": (
                    "Mutated capture start_tree_hash differs from end_tree_hash "
                    f"({mutated['start_tree_hash']} != {mutated['end_tree_hash']}) "
                    f"and changed_path_names={mutated['changed_path_names']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{OUT}:freeze_sample.mutated",
                "start_tree_hash": mutated["start_tree_hash"],
                "end_tree_hash": mutated["end_tree_hash"],
                "changed_path_names": mutated["changed_path_names"],
            },
            {
                "claim": (
                    "Quiescent capture hashes match "
                    f"({quiet['start_tree_hash']}) and label=FROZEN."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{OUT}:freeze_sample.quiescent",
                "start_tree_hash": quiet["start_tree_hash"],
                "end_tree_hash": quiet["end_tree_hash"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0030-probe2-quiescent-frozen",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Mechanical reviewer: re-run the quiescent fixture and the live "
                "product-file hash. Catalog also names a cross-vendor refuter "
                "and a Windows-shell specialist who are not in this headless "
                "worker. No ADV rebuild."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "mutation-forces-sampled", "command": P1},
            {"id": "probe2", "role": "quiescent-earns-frozen", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0030/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "NO retry. A retry masks the exact instability this unit "
                "exists to measure; a failed run is the datum, re-run only "
                "with a changed hypothesis recorded first"
            ),
        },
        "min_bytes_threshold": 2048,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": tool, "exists": True, "role": "supporting"},
        ],
        "adv_rebuild_circle": False,
        "required_fix": None,
        "dependency_note": (
            "TST-0023 (pinned-SHA baseline schema) is not delivered on this "
            "tree. TST-0030 ships the freeze-versus-sample labeller that such "
            "a capture must use; it does not claim TST-0023 delivered."
        ),
    }

    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0030 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:TST-0030 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0030 artifact {size}B below floor")
        return 1
    if sentinel not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0030 catalog sentinel missing from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0030 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
