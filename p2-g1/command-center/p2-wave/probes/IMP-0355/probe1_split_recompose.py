#!/usr/bin/env python3
"""Probe 1: split and recompose 8 independent compound fixtures; support trace.

Also both-states the support detector: a mutated composed answer that no
sub-council produced must FAIL support_check (overclaim class).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures" / "compounds.json"
MODULE = REPO / "tools" / "council" / "decompose.py"


def load_mod():
    sys.path.insert(0, str(MODULE.parent))
    import decompose as mod  # noqa: E402

    return mod


def main() -> int:
    if not MODULE.is_file():
        print("FAILED:IMP-0355-probe1 missing tools/council/decompose.py")
        return 1
    D = load_mod()
    pack = json.loads(FIXTURES.read_text(encoding="utf-8"))
    independent = pack["independent"]
    if len(independent) != 8:
        print(f"FAILED:IMP-0355-probe1 expected 8 fixtures got {len(independent)}")
        return 1

    rows = []
    fail = False
    for fx in independent:
        question = {
            "id": fx["id"],
            "text": fx["text"],
            "clauses": fx["clauses"],
        }
        result = D.run_independent_packet(question, fx["answers"])
        ok = bool(result.get("ok"))
        n_subs = len((result.get("split") or {}).get("subquestions") or [])
        support = result.get("support") or {}
        if not ok or n_subs < 2 or not support.get("ok"):
            fail = True
        if (result.get("split") or {}).get("dependency_pass_fired"):
            fail = True
        trace = [
            {
                "claim_id": r.get("claim_id"),
                "covered_by": r.get("covered_by"),
                "ok": r.get("ok"),
            }
            for r in support.get("rows") or []
        ]
        rows.append(
            {
                "id": fx["id"],
                "ok": ok,
                "n_subs": n_subs,
                "support_ok": bool(support.get("ok")),
                "trace": trace,
            }
        )
        print(
            f"fixture {fx['id']} ok={ok} n_subs={n_subs} "
            f"support_ok={support.get('ok')} claims={len(trace)}"
        )

    # Both-states for support: mutate fx-ind-01 composed output.
    first = independent[0]
    question = {
        "id": first["id"],
        "text": first["text"],
        "clauses": first["clauses"],
    }
    good = D.run_independent_packet(question, first["answers"])
    composed = D.ComposedAnswer(
        question_id=first["id"],
        text=good["composed"]["text"],
        claims=[
            D.load_claim(c, c.get("id") or "c", (c.get("supported_by") or [""])[0])
            for c in good["composed"]["claims"]
        ],
        sub_ids=list(good["composed"]["sub_ids"]),
        invented=False,
    )
    mutated = D.inject_unsupported_claim(composed, pack["overclaim"])
    loaded_answers = [D.load_sub_answer(a) for a in first["answers"]]
    bad_support = D.support_check(mutated, loaded_answers)
    good_support = D.support_check(composed, loaded_answers)
    if not good_support.ok:
        print("FAILED:IMP-0355-probe1 support detector failed on the good compose")
        fail = True
    if bad_support.ok or not bad_support.unsupported_ids:
        print("FAILED:IMP-0355-probe1 overclaim did not fail support_check")
        fail = True
    else:
        print(
            f"overclaim fired unsupported={bad_support.unsupported_ids} "
            f"good_ok={good_support.ok}"
        )

    passed = sum(1 for r in rows if r["ok"] and r["support_ok"] and r["n_subs"] >= 2)
    summary = {
        "probe": "probe1-split-recompose",
        "unit_id": "IMP-0355",
        "fixtures": 8,
        "passed": passed,
        "support_good_ok": good_support.ok,
        "support_overclaim_failed": (not bad_support.ok),
        "rows": rows,
        "pass": (not fail) and passed == 8,
    }
    print(json.dumps(summary, sort_keys=True))
    if fail or passed != 8:
        print("FAILED:IMP-0355-probe1 split/recompose/support")
        return 1
    print("SUCCESS:IMP-0355-probe1 split and recompose on 8 compound fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
