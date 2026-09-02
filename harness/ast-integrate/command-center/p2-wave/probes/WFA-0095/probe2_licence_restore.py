#!/usr/bin/env python3
"""Probe 2: independent union arithmetic, stricter licence, restore, mutant.

Does not call evaluate_collapse for the union/licence verdicts. Re-derives
required sets with frozenset difference, then compares those verdicts to
the policy engine and to the sealed artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import policy as P  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0095-duplicate-collapse-policy.json"
FIELDS = P.PRESERVED_SETS


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0095-probe2 {msg}")
    return 1


def as_set(values) -> frozenset[str]:
    if values is None:
        return frozenset()
    return frozenset(str(v) for v in values)


def reviewer_union(left: dict, right: dict, merged: dict) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for field in FIELDS:
        need = as_set(left.get(field)) | as_set(right.get(field))
        have = as_set(merged.get(field))
        lost = sorted(need - have)
        if lost:
            missing[field] = lost
    return missing


def reviewer_licence(left: dict, right: dict, merged: dict) -> str | None:
    """Independent join: numeric rank table copied here, not via licence_join."""
    rank = {
        "CC0-1.0": 0,
        "Unlicense": 0,
        "0BSD": 0,
        "MIT": 10,
        "BSD-2-Clause": 10,
        "BSD-3-Clause": 10,
        "ISC": 10,
        "Apache-2.0": 20,
        "MPL-2.0": 30,
        "LGPL-2.1-only": 40,
        "LGPL-3.0-only": 40,
        "GPL-2.0-only": 50,
        "GPL-3.0-only": 60,
        "AGPL-3.0-only": 70,
        "UNKNOWN": 100,
        "UNLICENSED": 100,
        "ALL-RIGHTS-RESERVED": 100,
    }
    a = left.get("licence_spdx")
    b = right.get("licence_spdx")
    ra = rank.get(str(a))
    rb = rank.get(str(b))
    if ra is None or rb is None:
        return None
    if ra > rb:
        want = a
    elif rb > ra:
        want = b
    elif a == b:
        want = a
    else:
        return None
    return str(want) if merged.get("licence_spdx") == want else None


def reviewer_admits(left: dict, right: dict, merged: dict) -> bool:
    if reviewer_union(left, right, merged):
        return False
    return reviewer_licence(left, right, merged) is not None


def main() -> int:
    fx = P.fixtures()
    mismatches = []
    for fid, fixture in fx.items():
        missing = reviewer_union(fixture["left"], fixture["right"], fixture["merged"])
        lic_ok = reviewer_licence(fixture["left"], fixture["right"], fixture["merged"])
        admits = reviewer_admits(fixture["left"], fixture["right"], fixture["merged"])
        engine = P.run_fixture(fixture)
        union_ok = not missing and lic_ok is not None
        print(
            f"recount id={fid} reviewer_union_ok={union_ok} "
            f"reviewer_admits={admits} engine_accepted={engine['accepted']} "
            f"engine_codes={engine['codes']} missing={missing}"
        )
        if fid == "union-preserving-no-edge":
            if not union_ok:
                mismatches.append(f"{fid}: reviewer should see union-ok")
            if engine["accepted"] or P.MISSING_DUPLICATE_OF not in engine["codes"]:
                mismatches.append(f"{fid}: engine must reject missing duplicate-of")
            continue
        if admits != engine["accepted"]:
            mismatches.append(
                f"{fid}: reviewer_admits={admits} engine={engine['accepted']}"
            )
        if fid == "union-preserving" and not engine.get("restore_ok"):
            mismatches.append(f"{fid}: restore_ok")

    if mismatches:
        return fail("recount disagreement " + " | ".join(mismatches))

    lossy = fx["planted-lossy-mechanism"]
    good = fx["union-preserving"]
    weak = fx["planted-licence-weakened"]

    if reviewer_admits(lossy["left"], lossy["right"], lossy["merged"]):
        return fail("reviewer admitted planted capability loss")
    if not reviewer_admits(good["left"], good["right"], good["merged"]):
        return fail("reviewer rejected union-preserving merge")
    if reviewer_licence(weak["left"], weak["right"], weak["merged"]) is not None:
        return fail("reviewer accepted MIT as governing over AGPL-3.0-only")
    if reviewer_licence(good["left"], good["right"], good["merged"]) != "AGPL-3.0-only":
        return fail("reviewer did not require AGPL-3.0-only on the admitted merge")

    engine_good = P.run_fixture(good)
    survivor_pre, absorbed = P.restore_from_edge(engine_good["edges"][0])
    if not P.records_equal(survivor_pre, good["left"]):
        return fail("restore survivor_pre != original survivor")
    if not P.records_equal(absorbed, good["right"]):
        return fail("restore absorbed != original absorbed")

    mutant = P.always_accept_mutant(
        lossy["left"], lossy["right"], lossy["merged"], lossy["survivor_id"]
    )
    if not mutant["accepted"]:
        return fail("always_accept_mutant did not accept planted loss")
    if not mutant["missing"].get(P.MECHANISMS):
        return fail("always_accept_mutant missing set empty; plant not visible")
    engine_lossy = P.run_fixture(lossy)
    if engine_lossy["accepted"]:
        return fail("real policy accepted planted loss — constraint is dead")

    if not OUT.is_file():
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    recorded = {
        row["fixture_id"]: row
        for row in (doc.get("evaluations") or [])
        if isinstance(row, dict)
    }
    for fid, fixture in fx.items():
        engine = P.run_fixture(fixture)
        rec = recorded.get(fid)
        if not isinstance(rec, dict):
            return fail(f"artifact missing evaluations[{fid}]")
        if rec.get("accepted") != engine["accepted"]:
            return fail(f"artifact accepted mismatch {fid}")
        if list(rec.get("codes") or []) != list(engine["codes"]):
            return fail(f"artifact codes mismatch {fid}")

    method = str((doc.get("reviewer") or {}).get("method") or "")
    if "frozenset" not in method.lower() and "set" not in method.lower():
        return fail("artifact reviewer.method does not claim independent set arithmetic")
    if (doc.get("reviewer") or {}).get("independent") is not True:
        return fail("artifact reviewer.independent is not true")
    if not (doc.get("controls") or {}).get("licence_weakened_rejected"):
        return fail("artifact did not record licence-weakened rejection")
    if not (doc.get("controls") or {}).get("restore_equals_preimage"):
        return fail("artifact did not record restore control")
    if not (doc.get("controls") or {}).get("always_accept_mutant_fails_planted_lossy"):
        return fail("artifact did not record always-accept mutant control")

    print("reviewer_independent=True disagreements=0")
    print("SUCCESS:WFA-0095-probe2 licence, restore, mutant agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
