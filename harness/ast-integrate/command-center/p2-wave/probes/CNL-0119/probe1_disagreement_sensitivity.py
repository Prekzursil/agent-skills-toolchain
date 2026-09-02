#!/usr/bin/env python3
"""Probe 1: mechanical disagreement rate + flip-sensitivity sweep.

Uses tabulator.py (dict / first-match IRV). Distinct from probe 2
(pointer-IRV / matrix Copeland recount).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import simulate as S  # noqa: E402
import tabulator as T  # noqa: E402
from schema_offline import results_section  # noqa: E402

OUT = HERE / "probe1-disagreement.raw.json"
ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0119-voting-method-differential-simulation-over-one-ballot-set.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0119-probe1 {msg}")
    return 1


def main() -> int:
    S.engines_match()
    live = S.report(engine=T)
    n = live["n_fixtures"]
    k = live["n_disagree"]
    rate = live["disagreement_rate"]
    if n != 9:
        return fail(f"expected 9 declared fixtures, got {n}")
    if k < 1:
        return fail("disagreement rate is 0; fixture set does not distinguish methods")
    if abs(rate - k / n) > 1e-15:
        return fail(f"rate {rate} is not k/n={k}/{n}")
    most = live["most_sensitive"]
    if int(most["n_winner_changes"]) <= 0:
        return fail("sensitivity sweep found no winner-changing flip")
    table = {r["method"]: r for r in live["sensitivity_table"]}
    if set(table) != set(T.METHODS):
        return fail("sensitivity table missing a method")
    for r in live["sensitivity_table"]:
        if r["n_flips_tried"] != 79:
            return fail(f"{r['method']} n_flips_tried {r['n_flips_tried']} != 79")
        expect = r["n_winner_changes"] / r["n_flips_tried"]
        if abs(r["rate"] - expect) > 1e-15:
            return fail(f"{r['method']} rate is not changes/flips")

    payload = {
        "probe": "probe1-disagreement-sensitivity",
        "unit_id": "CNL-0119",
        "n_fixtures": n,
        "n_disagree": k,
        "disagreement_rate": rate,
        "disagreeing_fixture_ids": live["disagreeing_fixture_ids"],
        "most_sensitive": most,
        "sensitivity_table": live["sensitivity_table"],
        "fixture_winners": {r["id"]: r["winners"] for r in live["fixtures"]},
        "pass": True,
    }

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        q = results_section(doc)
        if int(q.get("n_disagree") or -1) != k:
            return fail(f"artifact n_disagree {q.get('n_disagree')} != live {k}")
        if abs(float(q.get("disagreement_rate") or -1) - rate) > 1e-15:
            return fail("artifact disagreement_rate mismatch")
        art_table = {
            r["method"]: r for r in (q.get("sensitivity_table") or [])
        }
        for m, row in table.items():
            a = art_table.get(m) or {}
            if int(a.get("n_winner_changes") or -1) != row["n_winner_changes"]:
                return fail(f"artifact sensitivity mismatch on {m}")
        art_most = (q.get("most_sensitive") or {}).get("method")
        if art_most != most["method"]:
            return fail(f"artifact most_sensitive {art_most} != {most['method']}")
        payload["artifact_matches_live"] = True

    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"n_fixtures={n} n_disagree={k} disagreement_rate={rate:.6f} "
        f"most_sensitive={most['method']} n_winner_changes={most['n_winner_changes']}"
    )
    print("SUCCESS:CNL-0119-probe1 disagreement rate and sensitivity sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
