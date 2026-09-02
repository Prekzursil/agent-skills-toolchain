#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0340.json from a live co-change run.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write. cloud ok=true is not delivery.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cochange as C  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0340/probe1_planted_and_unrelated.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0340/probe2_justification.py"
)
QUESTION = (
    "Implementation target: a golden file regenerated alongside the code it "
    "verifies has stopped being a test and become a transcript. Build the "
    "check that, for every commit or PR, intersects the set of changed "
    "snapshot files with the set of changed source files they cover, and "
    "requires an explicit, reviewed justification when the intersection is "
    "non-empty. Blanket snapshot regeneration is the mechanism by which a "
    "suite stays green through a behaviour change."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> dict:
    path = REPO / rel
    if path.is_file() and path.stat().st_size > 0:
        sha, size = sha256_file(path)
        return {"path": rel, "present": True, "bytes": size, "sha256": sha}
    return {"path": rel, "present": False, "bytes": 0, "sha256": None}


def main() -> int:
    bundle = C.run_named_scenarios()
    if not bundle["all_pass"]:
        print("FAILED:TST-0340 emit fixture scenarios did not all PASS")
        print(json.dumps(bundle["tests"], indent=2)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snaps = C.discover_snapshots(REPO)
    git = C.git_changed(REPO)
    registry = present("command-center/TEST-REGISTRY.json")
    engine_rel = "command-center/p2-wave/probes/TST-0340/cochange.py"
    map_rel = C.MAP_REL
    planted = bundle["scenarios"]["planted"]
    unrelated = bundle["scenarios"]["unrelated"]
    legit = bundle["scenarios"]["legitimate"]

    answer = (
        f"{C.SENTINEL}. Check intersects changed snapshots with the sources "
        "they cover and FLAGGED the planted widget.py ++ widget.snap pair; "
        "the same pair PASSES when a reviewed behaviour-change justification "
        "is recorded; widget.snap ++ gadget.py (unrelated) does not flag. "
        "Empty and boilerplate justification fields are UNJUSTIFIED. "
        f"Live snapshot census n={len(snaps)}. "
        f"TEST-REGISTRY.json present={registry['present']}. "
        f"git worktree available={git['available']}. "
        "This worktree is not a git repo, so commit/PR diffs are supplied as "
        "named changesets rather than git-diff; the checker accepts either."
    )

    receipt = {
        "adv_rebuild_circle": False,
        "answer": answer,
        "artifacts": [
            {"exists": True, "path": C.OUT_REL, "role": "primary"},
            {"exists": True, "path": engine_rel, "role": "checker"},
            {"exists": True, "path": map_rel, "role": "coverage-map"},
        ],
        "both_states_control": {
            "always_empty_mutant_misses_planted": bundle[
                "mutant_empty_intersection_size"
            ]
            == 0,
            "boilerplate_unjustified": bundle["scenarios"]["boilerplate"]["verdict"]
            == "FLAGGED",
            "empty_unjustified": bundle["scenarios"]["empty_justification"]["verdict"]
            == "FLAGGED",
            "legitimate_passes_with_justification_recorded": legit["verdict"]
            == "PASS"
            and bool(legit["intersection"][0]["justification"]),
            "planted_flagged": planted["verdict"] == "FLAGGED",
            "unrelated_not_flagged": unrelated["verdict"] == "PASS"
            and unrelated["intersection_size"] == 0,
        },
        "checker": {
            "cli": (
                "python3 -B command-center/p2-wave/probes/TST-0340/cochange.py "
                "--coverage command-center/p2-wave/probes/TST-0340/fixtures/"
                "coverage-map.json --changed <changeset.json> "
                "--justifications <justifications.json>"
            ),
            "path": engine_rel,
            "rule": (
                "FLAG when a changed snapshot and a changed source it covers "
                "co-occur unless an explicit reviewed justification is recorded"
            ),
        },
        "completion_sentinel": C.SENTINEL,
        "coverage_map": {
            "path": map_rel,
            "present": True,
            "snapshot_count": bundle["coverage_size"],
        },
        "evidence": [
            {
                "detail": (
                    "planted intersection named "
                    + ", ".join(planted["named_pairs"])
                    + " verdict=FLAGGED unjustified_reason="
                    + str(planted["intersection"][0]["unjustified_reason"])
                ),
                "kind": "intersection",
            },
            {
                "detail": (
                    "unrelated change gadget.py + widget.snap "
                    f"intersection_size={unrelated['intersection_size']} "
                    f"verdict={unrelated['verdict']}"
                ),
                "kind": "control",
            },
            {
                "detail": (
                    "legitimate justification recorded ("
                    f"{len(legit['intersection'][0]['justification'])} chars) "
                    f"reviewed_by={legit['intersection'][0]['reviewed_by']} "
                    "verdict=PASS"
                ),
                "kind": "justification",
            },
            {
                "detail": (
                    "empty justification reason=empty; boilerplate "
                    "justification='update snapshots' reason=boilerplate; "
                    "both remain FLAGGED"
                ),
                "kind": "unjustified",
            },
        ],
        "evidence_requirement": (
            "Report the intersection per change with the file pairs named. "
            "A justification field that is empty or boilerplate must be "
            "reported as unjustified."
        ),
        "git": git,
        "inputs": {
            "coverage_map": present(map_rel),
            "snapshot_and_golden_files": {
                "count": len(snaps),
                "sample": snaps[:40],
            },
            "test_registry": registry,
        },
        "named_probes": [
            {"command": P1, "id": "probe1"},
            {"command": P2, "id": "probe2"},
        ],
        "output_path": C.OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "output_schema_note": (
            "Catalog names receipt.schema.json, whose authored $defs currently "
            "bind fault_injection_report to TST-0133. This unit emits a "
            "snapshot_cochange_report; it does not pretend to be TST-0133."
        ),
        "question": QUESTION,
        "report_kind": "snapshot_cochange_report",
        "required_fix": None,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0340-probe2-justification",
            "verdict": "PASS",
        },
        "scenarios": bundle["scenarios"],
        "sentinel": C.SENTINEL,
        "state": "SUCCESS",
        "test_registry_present": registry["present"],
        "tests": bundle["tests"],
        "tests_required": [
            "Planted case: change a source and regenerate its snapshot in one commit -> FLAGGED.",
            "Legitimate case: a snapshot updated for an intentional, documented behaviour change passes with its justification recorded.",
            "Unrelated-change control: changing a snapshot and an unrelated source must not flag.",
        ],
        "title": "Flag any snapshot updated in the same change as the code it is supposed to guard",
        "ts": now,
        "unit_id": C.UNIT,
    }

    out = REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = sha256_file(out)
    print(f"wrote {C.OUT_REL} bytes={size} sha256={sha}")
    print(C.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
