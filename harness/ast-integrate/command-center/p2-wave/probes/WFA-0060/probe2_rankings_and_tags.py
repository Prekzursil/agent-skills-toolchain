#!/usr/bin/env python3
"""Probe 2: independent re-derivation of both rankings and SINGLE-SOURCE tags.

Does not import ranker.py. Recomputes unique-upstream cardinality and
frequency from the fixture JSON, then checks the live artifact.

Both-states (re-run of this unit's control):
  GOOD — unique upstream set size is the independent count.
  BAD  — artifact-count is treated as the independent count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/wfa/WFA-0060-mechanism-leverage-ranking.json"
FIXTURE = HERE / "fixtures" / "incidence-matrix.json"
ECHO_ID = "mech.echo.planted-stale-brief"
FANIN_ID = "mech.fanin.blocking-barrier"
PARTIAL_ID = "mech.partial.shared-upstream-plus-one"
SINGLE_ID = "mech.single.strong-probe"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0060-probe2 {msg}")
    return 1


def independent_n(incidences: list[dict]) -> int:
    return len({str(i["upstream_id"]) for i in incidences})


def frequency_n(incidences: list[dict]) -> int:
    return len({str(i["artifact_id"]) for i in incidences})


def domain_n(incidences: list[dict]) -> int:
    by_up: dict[str, set[str]] = {}
    for inc in incidences:
        by_up.setdefault(str(inc["upstream_id"]), set()).add(str(inc["domain"]))
    domains: set[str] = set()
    for ds in by_up.values():
        domains.update(ds)
    return len(domains)


def leverage(indep: int, domains: int, severity: int, impact: int) -> int:
    return indep * domains * severity * impact


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0060" not in text:
        return fail("sentinel absent")

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_fix = {
        str(m["mechanism_id"]): m for m in fixture.get("mechanisms") or []
    }
    art_records = {
        str(r["mechanism_id"]): r for r in (doc.get("records") or [])
    }

    lev_list = doc.get("leverage_ranking") or []
    freq_list = doc.get("frequency_ranking") or []
    if len(lev_list) < 2 or len(freq_list) < 2:
        return fail("both rankings must be published")
    if {r["mechanism_id"] for r in lev_list} != {r["mechanism_id"] for r in freq_list}:
        return fail("ranking id sets differ")

    rf = doc.get("ranking_function") or {}
    inputs = [str(x) for x in (rf.get("inputs") or [])]
    excludes = [str(x) for x in (rf.get("excludes") or [])]
    if "frequency" in inputs or "agent_repeat_count" in inputs:
        return fail("ranking_function.inputs includes frequency")
    if "frequency" not in excludes:
        return fail("ranking_function.excludes must name frequency")

    mismatches = []
    for mid, mech in by_fix.items():
        incs = list(mech.get("incidences") or [])
        indep = independent_n(incs)
        freq = frequency_n(incs)
        rec = art_records.get(mid)
        if rec is None:
            return fail(f"artifact missing {mid}")
        if int(rec["independent_evidence"]) != indep:
            mismatches.append(f"{mid} independent {rec['independent_evidence']}!={indep}")
        if int(rec["frequency"]) != freq:
            mismatches.append(f"{mid} frequency {rec['frequency']}!={freq}")
        tagged = "SINGLE-SOURCE" in list(rec.get("tags") or [])
        if (indep == 1) != tagged:
            mismatches.append(f"{mid} SINGLE-SOURCE tag {tagged} indep={indep}")
        if indep == 1 and rec.get("single_source") is not True:
            mismatches.append(f"{mid} single_source field false")
    if mismatches:
        return fail("; ".join(mismatches))

    echo = by_fix[ECHO_ID]
    replay = by_fix["mech.replay.deterministic"]
    echo_incs = echo["incidences"]
    replay_incs = replay["incidences"]
    echo_good = leverage(
        independent_n(echo_incs),
        domain_n(echo_incs),
        int(echo["severity"]),
        int(echo["decision_impact"]),
    )
    echo_bad = leverage(
        frequency_n(echo_incs),
        domain_n(echo_incs),
        int(echo["severity"]),
        int(echo["decision_impact"]),
    )
    replay_lev = leverage(
        independent_n(replay_incs),
        domain_n(replay_incs),
        int(replay["severity"]),
        int(replay["decision_impact"]),
    )
    if echo_good >= replay_lev:
        return fail("reviewer GOOD arm: collapsed echo does not lose to replay")
    if echo_bad <= replay_lev:
        return fail("reviewer BAD arm: frequency-as-n did not beat replay")

    fanin = art_records[FANIN_ID]
    if int(fanin["independent_evidence"]) != int(fanin["frequency"]):
        return fail("fanin independent cluster was over-collapsed")
    if int(fanin["independent_evidence"]) != 3:
        return fail("fanin independent_evidence want=3")
    if int(fanin["cross_domain_convergence"]) != 3:
        return fail("fanin cross_domain_convergence want=3")

    single = art_records[SINGLE_ID]
    if "SINGLE-SOURCE" not in single["tags"]:
        return fail("strong single probe missing SINGLE-SOURCE")
    if int(single["leverage_score"]) <= int(art_records[ECHO_ID]["leverage_score"]):
        return fail("single strong probe did not outrank weaker echo")

    partial = art_records[PARTIAL_ID]
    if int(partial["frequency"]) != 3 or int(partial["independent_evidence"]) != 2:
        return fail("partial collapse 3→2 not visible on artifact")

    if not doc.get("disagreements"):
        return fail("disagreements list empty; frequency ranking would hide echo")

    payload = {
        "both_states": {
            "bad_echo_score": echo_bad,
            "good_echo_score": echo_good,
            "replay_score": replay_lev,
        },
        "frequency_ranking_len": len(freq_list),
        "leverage_ranking_len": len(lev_list),
        "pass": True,
        "probe": "probe2-rankings-and-tags",
        "reviewer": "independent-unique-upstream-cardinality",
        "unit_id": "WFA-0060",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"reviewer_good={echo_good} reviewer_bad={echo_bad} replay={replay_lev} "
        f"fanin_n={fanin['independent_evidence']} single_tag=SINGLE-SOURCE"
    )
    print(
        "SUCCESS:WFA-0060-probe2 both rankings published; "
        "SINGLE-SOURCE tagged; reviewer re-ran both-states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
