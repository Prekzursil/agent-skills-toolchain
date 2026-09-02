#!/usr/bin/env python3
"""Probe 2: detector controls. Independent of probe 1's verdict.

Controls:
  * planted ambiguous M-16 stays ambiguous (not guessed)
  * MECH-16 is not reported as bare M-16
  * quoted example is mention, not a live use
  * decision-log fixture is stale present-tense with zero MECH tokens
  * planted M-99 is absent
  * both-states: pre-fix intersection >0, post-fix architecture bare M-NN = 0
  * dropping guessed=false on an ambiguous row must fail the no-guess checker
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = REPO / E.OUTPUT_REL


def rows(doc: dict, suffix: str, token: str | None = None) -> list[dict]:
    body = E.report_of(doc)
    out = []
    for r in body.get("references") or []:
        if not str(r.get("path") or "").endswith(suffix):
            continue
        if token is not None and r.get("token") != token:
            continue
        out.append(r)
    return out


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0072-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if E.SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0072-probe2 sentinel-absent")
        return 1

    body = E.report_of(doc)

    amb = rows(doc, "ambiguous-scratch.md", "M-16")
    print(f"ambiguous_rows={len(amb)} cls={[r.get('classification') for r in amb]}")
    if not amb:
        print("FAILED:CNF-0072-probe2 planted ambiguous M-16 not found")
        return 1
    if any(r.get("classification") != "ambiguous" or r.get("resolved_namespace") or r.get("guessed") for r in amb):
        print("FAILED:CNF-0072-probe2 ambiguous was resolved or guessed")
        return 1

    mech_fp = rows(doc, "mech-false-positive.md")
    bare = [r for r in mech_fp if r["token"].startswith("M-")]
    mech = [r for r in mech_fp if r["token"] == "MECH-16"]
    print(f"mech_fp bare={len(bare)} MECH-16={len(mech)}")
    if bare:
        print("FAILED:CNF-0072-probe2 MECH-16 reported as bare M-NN")
        return 1
    if not mech or any(r.get("classification") != "resolves-uniquely" for r in mech):
        print("FAILED:CNF-0072-probe2 MECH-16 did not resolve uniquely")
        return 1

    mention = rows(doc, "mention-quote.md", "M-16")
    print(f"mention_rows={len(mention)} role={[r.get('role') for r in mention]}")
    if not mention or any(r.get("classification") != "mention" or r.get("role") != "mention" for r in mention):
        print("FAILED:CNF-0072-probe2 quoted example not classified as mention")
        return 1

    absent = rows(doc, "absent-scratch.md", "M-99")
    print(f"absent_rows={len(absent)} cls={[r.get('classification') for r in absent]}")
    if not absent or any(r.get("classification") != "absent" or r.get("guessed") for r in absent):
        print("FAILED:CNF-0072-probe2 M-99 was not left absent")
        return 1

    clog = (body.get("decision_log") or {}).get("control") or {}
    print(f"decision_log status={clog.get('status')} mech={clog.get('mech_token_count')} stale={clog.get('stale_present_tense')}")
    if clog.get("status") != "STALE" or clog.get("mech_token_count") != 0 or clog.get("stale_present_tense") is not True:
        print("FAILED:CNF-0072-probe2 control decision log is not stale")
        return 1
    live_log = (body.get("decision_log") or {}).get("live") or {}
    if live_log.get("present") is True and live_log.get("stale_present_tense") is None:
        print("FAILED:CNF-0072-probe2 live decision log present but staleness unmeasured")
        return 1

    both = body.get("both_states") or {}
    pre = both.get("pre_fix_shared_bare_m") or []
    post = both.get("post_fix_architecture_bare_m") or []
    print(f"both_states pre={pre} post={post}")
    if len(pre) < 1 or len(post) != 0:
        print("FAILED:CNF-0072-probe2 both-states control failed")
        return 1

    ns_ids = {n["id"] for n in body.get("namespaces") or []}
    print(f"control_namespaces={sorted(ns_ids)}")
    if ns_ids != {E.NS_OPTION, E.NS_MECH, E.NS_HARNESS, E.NS_MISSION}:
        print("FAILED:CNF-0072-probe2 expected four control namespaces")
        return 1

    mutant = copy.deepcopy(body)
    mutated = False
    for r in mutant["references"]:
        if r.get("classification") == "ambiguous":
            r["resolved_namespace"] = E.NS_OPTION
            r["guessed"] = True
            mutated = True
            break
    if not mutated:
        print("FAILED:CNF-0072-probe2 no ambiguous row to mutate")
        return 1
    viol = E.no_guess_violation(mutant["references"])
    print(f"mutant_guess_violations={len(viol)}")
    if not viol:
        print("FAILED:CNF-0072-probe2 no-guess checker accepted a guessed ambiguous row")
        return 1

    print("SUCCESS:CNF-0072-probe2 controls reviewer-independent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
