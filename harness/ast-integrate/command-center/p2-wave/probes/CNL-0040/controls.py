"""Both-states and negative-control measurements for CNL-0040."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402
import runtime as R  # noqa: E402


def family_count_control() -> dict:
    enum = F.enumerate_family()
    good_ids = list(enum["ids"])
    bad_ids = list(good_ids) + ["P99"]
    silent = len(good_ids) == F.EXPECTED_N
    fires = len(bad_ids) != F.EXPECTED_N
    return {
        "good_n": len(good_ids),
        "bad_n": len(bad_ids),
        "expected_n": F.EXPECTED_N,
        "silent_on_good": silent,
        "fires_on_bad": fires,
        "good_ids": good_ids,
        "bad_ids": bad_ids,
        "match": bool(enum["match"]),
        "library": enum["library"],
    }


def gatekeeper_both_states() -> dict:
    good = R.execute_named("good", "P14")
    bad = R.execute_named("bad", "P14-gatekeeper-decides")
    return {
        "silent_on_good": good["fires"] is False,
        "fires_on_bad": bad["fires"] is True,
        "good_violations": good["violations"],
        "bad_violations": bad["violations"],
        "bad_codes": [v["code"] for v in bad["violations"]],
        "good_admitted": good["admitted"],
        "good_excluded": good["excluded"],
        "good": {k: good[k] for k in ("ok", "fires", "admitted", "excluded", "verdict", "violations")},
        "bad": {k: bad[k] for k in ("ok", "fires", "admitted", "excluded", "verdict", "violations")},
    }


def extra_planted() -> dict:
    cases = {
        "P17-judge-breaks-hung": "HUNG_BROKEN_BY_OFFICER",
        "P18-single-key-admit": "SINGLE_KEY_ADMIT",
        "P19-chair-declares-consensus": "CHAIR_DECLARED_CONSENSUS",
    }
    out = {}
    all_ok = True
    for name, code in cases.items():
        res = R.execute_named("bad", name)
        fired = res["fires"] is True and code in [v["code"] for v in res["violations"]]
        out[name] = {
            "expected_code": code,
            "fired": fired,
            "codes": [v["code"] for v in res["violations"]],
        }
        all_ok = all_ok and fired
    return {"all_fired": all_ok, "cases": out}


def negative_control() -> dict:
    """What the check does on the state it is meant to reject."""
    bad = R.execute_named("bad", "P14-gatekeeper-decides")
    statement = (
        "On planted-bad fixture P14-gatekeeper-decides the judge is in both "
        "officers and deciders and casts a verdict ballot. admissibility_invariants "
        "FIRES with GATEKEEPER_IS_DECIDER (and OFFICER_CAST_VERDICT). That is the "
        "state the check is meant to reject: an admissibility officer who becomes "
        "the decider."
    )
    return {
        "fixture": "P14-gatekeeper-decides",
        "fires": bad["fires"] is True,
        "codes": [v["code"] for v in bad["violations"]],
        "violations": bad["violations"],
        "statement": statement,
        "verbatim": json.dumps(bad["violations"], sort_keys=True),
    }


def all_good_executable() -> dict:
    results = R.execute_all_good()
    rows = {}
    all_ok = True
    for pid, res in results.items():
        ok = res["fires"] is False and res.get("executable") is True
        rows[pid] = {
            "ok": ok,
            "fires": res["fires"],
            "admitted": res["admitted"],
            "excluded": res["excluded"],
            "verdict": res["verdict"],
            "violations": res["violations"],
            "record_id": res["record_id"],
        }
        all_ok = all_ok and ok
    return {"all_ok": all_ok, "n": len(rows), "rows": rows}


def measure() -> dict:
    enum = F.enumerate_family()
    gate = gatekeeper_both_states()
    count = family_count_control()
    neg = negative_control()
    goods = all_good_executable()
    extra = extra_planted()
    ok = (
        enum["match"]
        and gate["silent_on_good"]
        and gate["fires_on_bad"]
        and count["silent_on_good"]
        and count["fires_on_bad"]
        and neg["fires"]
        and goods["all_ok"]
        and extra["all_fired"]
        and goods["n"] == F.EXPECTED_N
    )
    return {
        "ok": ok,
        "enumeration": enum,
        "gatekeeper_both_states": gate,
        "family_count_both_states": count,
        "negative_control": neg,
        "all_good": goods,
        "extra_planted": extra,
    }
