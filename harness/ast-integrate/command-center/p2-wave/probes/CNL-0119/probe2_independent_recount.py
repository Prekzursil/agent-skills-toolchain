#!/usr/bin/env python3
"""Probe 2: independent recount + both-states disagreement detector.

Does not import tabulator.py or simulate.py. Re-tabulates from
fixtures/profiles.json with recount.py (pointer IRV, n-by-n pairwise matrix).
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recount as R  # noqa: E402
from schema_offline import (  # noqa: E402
    catalog_validator,
    negative_control_section,
    results_section,
)

OUT = HERE / "probe2-independent-recount.raw.json"
ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0119-voting-method-differential-simulation-over-one-ballot-set.md"
)
SCHEMA = REPO / "command-center/schema/council-simulation-spec.schema.json"
PROFILES = HERE / "fixtures" / "profiles.json"
METHODS = list(R.METHODS)
NEGATIVE = "unanimous-3"
PLANTED = "spoiler-triple"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0119-probe2 {msg}")
    return 1


def demote_first_to_last(ranking: list[str]) -> list[str]:
    if len(ranking) < 2:
        return list(ranking)
    return list(ranking[1:]) + [ranking[0]]


def flipped(profile: dict, voter: str) -> dict:
    p = deepcopy(profile)
    for b in p["ballots"]:
        if b["voter"] == voter:
            b["ranking"] = demote_first_to_last(list(b["ranking"]))
            return p
    raise KeyError(voter)


def detector(winners: dict[str, str]) -> str:
    return "FIRE" if len(set(winners.values())) > 1 else "SILENT"


def main() -> int:
    if "tabulator" in sys.modules or "simulate" in sys.modules:
        return fail("tabulator/simulate imported; recount is not independent")
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))["profiles"]
    by_id = {p["id"]: p for p in profiles}

    rows = []
    changes = {m: 0 for m in METHODS}
    n_flips = 0
    for p in profiles:
        w = R.winners(p)
        rows.append({"id": p["id"], "winners": w, "disagree": detector(w) == "FIRE"})
        for b in p["ballots"]:
            n_flips += 1
            fw = R.winners(flipped(p, b["voter"]))
            for m in METHODS:
                if fw[m] != w[m]:
                    changes[m] += 1

    n = len(rows)
    k = sum(1 for r in rows if r["disagree"])
    rate = k / n
    table = [
        {
            "method": m,
            "n_flips_tried": n_flips,
            "n_winner_changes": changes[m],
            "rate": changes[m] / n_flips,
        }
        for m in METHODS
    ]
    ranked = sorted(table, key=lambda r: (-r["n_winner_changes"], -r["rate"], r["method"]))
    most = ranked[0]["method"]

    neg = R.winners(by_id[NEGATIVE])
    planted = R.winners(by_id[PLANTED])
    if detector(neg) != "SILENT":
        return fail(f"negative control FIRED on {NEGATIVE}: {neg}")
    if len(set(neg.values())) != 1 or next(iter(neg.values())) != "A":
        return fail(f"unanimous winner not A: {neg}")
    if detector(planted) != "FIRE":
        return fail(f"planted spoiler SILENT: {planted}")
    if planted["plurality"] != "A" or planted["irv"] != "C" or planted["borda"] != "B":
        return fail(f"spoiler-triple winners drifted: {planted}")

    validator = catalog_validator()
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    g_errs = list(validator.iter_errors(garbage))
    if not g_errs:
        return fail("schema accepted garbage")

    payload = {
        "probe": "probe2-independent-recount",
        "unit_id": "CNL-0119",
        "n_fixtures": n,
        "n_disagree": k,
        "disagreement_rate": rate,
        "most_sensitive": most,
        "sensitivity_table": table,
        "negative_control_state": NEGATIVE,
        "negative_control_action": "SILENT: every method elects A",
        "planted_state": PLANTED,
        "planted_action": "FIRE: plurality=A irv=C borda/approval/score/copeland=B",
        "negative_winners": neg,
        "planted_winners": planted,
        "schema_garbage_error_count": len(g_errs),
        "pass": True,
    }

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        errs = list(validator.iter_errors(doc))
        if errs:
            return fail(f"artifact schema {errs[0].message}")
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:CNL-0119" not in text:
            return fail("sentinel absent")
        q = results_section(doc)
        if int(q.get("n_disagree") or -1) != k:
            return fail(
                f"recount n_disagree {k} != artifact {q.get('n_disagree')}"
            )
        if abs(float(q.get("disagreement_rate") or -1) - rate) > 1e-15:
            return fail("recount disagreement_rate disagreement")
        art_fix = {r["id"]: r["winners"] for r in (q.get("fixtures") or [])}
        for r in rows:
            if art_fix.get(r["id"]) != r["winners"]:
                return fail(f"winner disagreement on {r['id']}")
        art_table = {r["method"]: r for r in (q.get("sensitivity_table") or [])}
        for row in table:
            a = art_table.get(row["method"]) or {}
            if int(a.get("n_winner_changes") or -1) != row["n_winner_changes"]:
                return fail(f"sensitivity recount mismatch {row['method']}")
        if (q.get("most_sensitive") or {}).get("method") != most:
            return fail("most_sensitive recount mismatch")
        nc = negative_control_section(doc)
        if "SILENT" not in str(nc.get("verbatim") or ""):
            return fail("artifact negative_control missing SILENT verbatim")
        payload["artifact_matches_recount"] = True

    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"recount n_disagree={k}/{n} rate={rate:.6f} most_sensitive={most} "
        f"schema_garbage_errors={len(g_errs)}"
    )
    print(
        "NEGATIVE-CONTROL verbatim: the disagreement check is SILENT on "
        "unanimous-3 (every method elects A) and FIRES on spoiler-triple "
        "(plurality=A, irv=C, borda=B)."
    )
    print("SUCCESS:CNL-0119-probe2 independent recount both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
