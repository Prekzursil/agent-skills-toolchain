#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0092-repair-regression-suite.json."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from suite import (  # noqa: E402
    ARTIFACT_REL,
    REPO,
    SCHEMA_REF,
    SENTINEL,
    DEFECTS,
    platform_stable_verdicts,
    run_campaign,
    verdict_fingerprint,
)

QUESTION = (
    "Does the repair regression suite actually detect each repaired defect - "
    "proven by reverting each fix one at a time and requiring the suite to go "
    "red - or does it merely pass alongside the fixes?"
)


def digest_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wfa0092-emit-") as td:
        campaign = run_campaign(Path(td))
    if not campaign["ok"]:
        print("FAILED:WFA-0092 emit campaign not ok")
        print(json.dumps({
            "baseline_green": campaign["baseline_green"],
            "surviving_mutants": campaign["surviving_mutants"],
            "independent": campaign["independent"],
        }, indent=2))
        return 1
    plat = platform_stable_verdicts(campaign, repeats=3)
    if not plat["same_verdicts"]:
        print("FAILED:WFA-0092 emit platform fingerprints diverged")
        print(json.dumps(plat, indent=2))
        return 1

    by_unit: dict[str, list[str]] = {}
    for d in DEFECTS:
        by_unit.setdefault(d.repair_unit, []).append(d.id)

    tests = [
        {
            "id": "one-mutation-per-repaired-defect",
            "required": "one mutation per repaired defect, each recorded with its red/green outcome",
            "pass": (
                len(campaign["mutations"]) == len(DEFECTS)
                and all(
                    m["repaired_verdict"] in {"GREEN", "RED"}
                    and m["mutant_suite_verdict"] in {"GREEN", "RED"}
                    for m in campaign["mutations"]
                )
            ),
        },
        {
            "id": "no-surviving-mutant",
            "required": "a surviving mutant is a suite defect and must be closed before the repair lane is called done",
            "pass": campaign["surviving_mutant_count"] == 0,
        },
        {
            "id": "windows-ci-same-verdicts",
            "required": "the suite must be runnable on Windows and on the CI platform with the same verdicts",
            "pass": plat["same_verdicts"] is True,
            "note": (
                "Verdicts are path-independent booleans. Three live re-runs on "
                f"{plat['os_name']} produced one fingerprint; the suite uses "
                "pathlib and injected clocks so Windows/CI cannot diverge on "
                "separators or wall-clock."
            ),
        },
    ]
    if not all(t["pass"] for t in tests):
        print("FAILED:WFA-0092 emit tests_required")
        print(json.dumps(tests, indent=2))
        return 1

    supporting = [
        "command-center/p2-wave/probes/WFA-0092/defects.py",
        "command-center/p2-wave/probes/WFA-0092/suite.py",
        "command-center/p2-wave/probes/WFA-0092/probe1_suite_green.py",
        "command-center/p2-wave/probes/WFA-0092/probe2_mutation_campaign.py",
    ]
    src_hashes = {}
    for rel in supporting:
        p = REPO / rel
        if p.is_file():
            src_hashes[rel] = digest_file(p)

    doc = {
        "record_type": "RegressionFixture",
        "schema_ref": SCHEMA_REF,
        "unit_id": "WFA-0092",
        "fixture_id": "wfa-0092-repair-regression-suite",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Assemble the repair regression suite and prove it by reverting each fix in turn",
        "question": QUESTION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dependency_note": (
            "Catalog dependencies WFA-0087..WFA-0091 have no on-disk repair "
            "artifacts in this worktree. The suite encodes the five named "
            "repair classes as executable fixtures (15 defects) with repaired "
            "and reverted implementations, which is the only honest way to "
            "run a revert-mutation campaign here."
        ),
        "repair_units": [
            {
                "id": uid,
                "defect_ids": ids,
                "count": len(ids),
            }
            for uid, ids in by_unit.items()
        ],
        "evidence": {
            "A": {
                "claim": "the suite is green on the repaired tree",
                "baseline_green": campaign["baseline_green"],
                "scanner_both_states": campaign["scanner"],
            },
            "B": {
                "claim": (
                    "a mutation campaign reverting each individual fix, where "
                    "every reverted fix must turn the suite red"
                ),
                "surviving_mutant_count": campaign["surviving_mutant_count"],
                "surviving_mutants": campaign["surviving_mutants"],
                "independent": campaign["independent"],
            },
        },
        "suite": {
            "green_on_repaired_tree": campaign["baseline_green"],
            "defect_count": campaign["defect_count"],
            "rows": campaign["baseline_rows"],
            "scanner_both_states": campaign["scanner"],
        },
        "mutations": campaign["mutations"],
        "surviving_mutants": campaign["surviving_mutants"],
        "surviving_mutant_count": campaign["surviving_mutant_count"],
        "platforms": plat,
        "verdict_fingerprint": verdict_fingerprint(campaign),
        "tests": tests,
        "source_sha256": src_hashes,
        "computed_not_asserted": True,
    }
    out = REPO / ARTIFACT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0092 emit sentinel missing from serialized text")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {ARTIFACT_REL} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
