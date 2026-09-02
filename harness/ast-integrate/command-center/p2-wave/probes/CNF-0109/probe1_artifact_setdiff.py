#!/usr/bin/env python3
"""Named probe 1: artifact-derived closure vs SBOM, both directions.

Must inspect the wheel, not the lockfile the SBOM was generated from.
A transitive dist missing from the SBOM is scored the same as a direct miss.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    APP,
    DIRECT,
    PHANTOM,
    PLANTED,
    TRANSITIVE,
    closure_from_wheel,
    diff_sets,
    generate_sbom_from_lockfile,
    key,
    parse_sbom,
    write_lockfile,
    write_wheel,
)

ART = REPO / "command-center/confirmation/CNF-0109-sbom-completeness.json"
SENTINEL = (
    "SUCCESS:CNF-0109 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the closure was computed "
    "from the artifact and the unregenerated-SBOM control was detected. Any "
    "other terminal state is FAILED:CNF-0109 <classification> with the "
    "diagnostic tail attached."
)


def _pairs(rows) -> set[tuple[str, str]]:
    return {key(r["name"], r["version"]) for r in rows}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0109-p1-") as tmp:
        root = Path(tmp)
        wheel = write_wheel(root / "cnf0109_plugin-1.0.0-py3-none-any.whl", include_planted=True)
        lock = write_lockfile(root / "declared-lock.txt")
        sbom = generate_sbom_from_lockfile(lock, root / "sbom.cdx.json")
        clos = closure_from_wheel(wheel)
        sbom_set = parse_sbom(sbom)
        diff = diff_sets(clos.components, sbom_set)

    planted = key(*PLANTED)
    phantom = key(*PHANTOM)
    direct = key(*DIRECT)
    trans = key(*TRANSITIVE)
    app = key(*APP)

    if planted not in clos.components:
        print("FAILED:CNF-0109-probe1 planted dist missing from artifact closure")
        return 1
    if phantom in clos.components:
        print("FAILED:CNF-0109-probe1 phantom listed dist appeared in artifact closure")
        return 1
    if planted not in diff.artifact_only:
        print("FAILED:CNF-0109-probe1 planted not in ships-but-absent")
        return 1
    if phantom not in diff.sbom_only:
        print("FAILED:CNF-0109-probe1 phantom not in listed-but-does-not-ship")
        return 1
    for need in (app, direct, trans):
        if need not in diff.both:
            print(f"FAILED:CNF-0109-probe1 declared control {need} not in both sets")
            return 1
    if TRANSITIVE[0] not in {dst for _, dst in clos.intra_artifact_requires}:
        print("FAILED:CNF-0109-probe1 transitive Requires-Dist edge not observed in artifact")
        return 1
    if DIRECT[0] not in clos.imported_dists or TRANSITIVE[0] not in clos.imported_dists:
        print("FAILED:CNF-0109-probe1 runtime import closure missed a bundled dist")
        return 1
    if "lockfile" in clos.method.lower() and "not opened" not in clos.method.lower():
        print("FAILED:CNF-0109-probe1 closure method looks circular")
        return 1

    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0109-probe1 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0109":
        print("FAILED:CNF-0109-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0109-probe1 self-declared", doc.get("state"))
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0109-probe1 catalog sentinel absent")
        return 1
    rec_absent = _pairs(doc.get("ships_but_absent") or [])
    rec_phantom = _pairs(doc.get("listed_but_does_not_ship") or [])
    if rec_absent != diff.artifact_only:
        print("FAILED:CNF-0109-probe1 ships_but_absent drift", sorted(rec_absent), sorted(diff.artifact_only))
        return 1
    if rec_phantom != diff.sbom_only:
        print("FAILED:CNF-0109-probe1 listed_but_does_not_ship drift")
        return 1
    method = doc.get("closure_method") or {}
    if method.get("computed_from_artifact") is not True:
        print("FAILED:CNF-0109-probe1 closure not computed from artifact")
        return 1
    if method.get("not_from_sbom_generating_manifest") is not True:
        print("FAILED:CNF-0109-probe1 circular-derivation flag missing")
        return 1

    payload = {
        "ships_but_absent": diff.ships_but_absent,
        "listed_but_does_not_ship": diff.listed_but_does_not_ship,
        "in_both": diff.in_both,
        "imported_dists": sorted(clos.imported_dists),
        "intra_artifact_requires": clos.intra_artifact_requires,
        "method": clos.method,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"absent={len(diff.artifact_only)} phantom={len(diff.sbom_only)} "
        f"both={len(diff.both)} planted_detected=True"
    )
    print("SUCCESS:CNF-0109-probe1 artifact-vs-sbom both-direction setdiff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
