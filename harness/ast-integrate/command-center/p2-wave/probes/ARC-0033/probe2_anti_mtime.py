#!/usr/bin/env python3
"""Probe 2: anti-mtime stall rule, reviewer-added mode, overclaim locus.

Stall predicates must not read file mtimes. A planted mtime-only mutant
must fail to distinguish the hung-unit pair (identical SHARED_MTIME).
Reviewer must add a mode the author list missed. REFUTED claims must
name SENTENCE vs DESIGN.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import reviewer as R  # noqa: E402
import traces as T  # noqa: E402

ART = REPO / "command-center/phase3/A5/FAILURE-MODES.json"
DESIGN = REPO / "command-center/phase3/A5/DESIGN.json"
NOW = 2000.0
MAX_AGE = 500.0


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0033-probe2 {msg}")
    return 1


def main() -> int:
    T.ensure_on_disk()
    report = E.anti_mtime_report()
    print(json.dumps(report))
    if not report.get("no_mtime_in_stall_signals"):
        return fail("stall predicate lists an mtime signal")

    hung_bad, hung_good = T.PAIRS["FM-HUNG-BLOCKS-BATCH"]
    our_bad = E.evaluate("FM-HUNG-BLOCKS-BATCH", hung_bad)
    our_good = E.evaluate("FM-HUNG-BLOCKS-BATCH", hung_good)
    mutant_bad = E.mtime_only_stall(hung_bad, NOW, MAX_AGE)
    mutant_good = E.mtime_only_stall(hung_good, NOW, MAX_AGE)
    print(
        f"hung_our bad={our_bad} good={our_good} "
        f"mtime_only bad={mutant_bad} good={mutant_good}"
    )
    if not our_bad or our_good:
        return fail("orchestrator stall predicate did not distinguish hung pair")
    if mutant_bad != mutant_good:
        return fail("mtime-only mutant distinguished traces that share mtime")
    if not mutant_bad:
        return fail("mtime-only mutant did not fire on the shared-old-mtime pair")

    if DESIGN.is_file():
        # Honest residual: if DESIGN later appears, this probe still must not
        # claim it was the source of the field names written today.
        print("note A5 DESIGN.json is present; field names remain probe-contract")
    else:
        print("A5 DESIGN.json absent as recorded")

    if not ART.is_file():
        return fail("FAILURE-MODES.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:ARC-0033" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    anti = doc.get("anti_mtime") or {}
    if anti.get("no_mtime_in_stall_signals") is not True:
        return fail("artifact anti_mtime flag false")
    if anti.get("mtime_only_mutant_cannot_distinguish_hung_pair") is not True:
        return fail("artifact missing mtime-only control")

    for spec in E.PREDICATES.values():
        if spec.get("stall_predicate"):
            signals = set(spec.get("signals") or [])
            if signals & E.FORBIDDEN_STALL_SIGNALS:
                return fail(f"engine stall signals include mtime {spec['id']}")
    for row in doc.get("author_failure_modes") or []:
        if row.get("stall_predicate") and set(row.get("signals") or []) & E.FORBIDDEN_STALL_SIGNALS:
            return fail(f"artifact stall mode uses mtime {row.get('id')}")

    author_ids = {m.get("id") for m in (doc.get("author_failure_modes") or [])}
    added = (doc.get("reviewer") or {}).get("added_failure_mode") or {}
    if added.get("id") != R.ADDED_MODE["id"]:
        return fail("reviewer added mode missing")
    if added.get("id") in author_ids:
        return fail("reviewer mode was already on the author list")
    if added.get("author_missed") is not True:
        return fail("reviewer mode not marked author_missed")
    if doc.get("reviewer", {}).get("scope_not_agreement") is not True:
        return fail("reviewer scope_not_agreement not true")
    if doc.get("reviewer", {}).get("enumeration_certified_against_47") is True:
        return fail("overclaim: certified 47 seeded classes")

    refuted = [c for c in (doc.get("claims") or []) if c.get("verdict") == "REFUTED"]
    if len(refuted) < 1:
        return fail("no REFUTED claim")
    for c in refuted:
        if c.get("defect_locus") not in {"DESIGN", "SENTENCE"}:
            return fail(f"{c.get('id')} REFUTED missing defect_locus")

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant.get("claims") or []:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        return fail("could not plant defect_locus mutant")
    plant_ok = any(
        r.get("verdict") == "REFUTED" and "defect_locus" not in r
        for r in mutant["claims"]
    )
    print(f"defect_locus_mutant_detectable={plant_ok}")
    if not plant_ok:
        return fail("planted missing defect_locus not visible")

    if doc.get("a5_design_present") is True:
        return fail("artifact claims A5 DESIGN.json present")
    print("SUCCESS:ARC-0033-probe2 anti-mtime reviewer-added-mode overclaim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
