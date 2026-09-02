#!/usr/bin/env python3
"""Probe 1: break each of the 12 conditions; the record must REJECTED for that condition.

Also: golden CERTIFIED, PROVISIONAL on NOT-CHECKED reviewer, exit-zero-missing
REJECTED on C2, N/A never counted as pass, unreasoned N/A fail-closed.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.foundry.certification_gate import certify_workflow  # noqa: E402
from tools.foundry.completion_predicate import (  # noqa: E402
    CERTIFIED,
    FAIL,
    NA,
    PASS,
    PROVISIONAL,
    REJECTED,
    UNKNOWN,
    evaluate,
)
import subjects as S  # noqa: E402

ART = (
    REPO
    / "command-center/foundry/"
    / "WFA-0134-bind-the-shared-12-condition-completion-predicate-to.json"
)


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0134-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 512:
        return _fail("artifact missing or tiny")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0134" not in text:
        return _fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return _fail(f"self-declared {doc.get('state')}")

    with tempfile.TemporaryDirectory(prefix="wfa0134-p1-") as tmp_s:
        root = Path(tmp_s)
        golden = S.materialize_golden(root)
        vg = certify_workflow(golden, repo=REPO)
        if vg.record != CERTIFIED:
            return _fail(f"golden not CERTIFIED: {vg.record} {vg.to_dict()}")
        if any(c.status != PASS for c in vg.conditions):
            return _fail(f"golden non-PASS {vg.statuses()}")

        mutant_rows = []
        for cid in range(1, 13):
            sub = S.materialize_mutant(root, cid)
            vm = certify_workflow(sub, repo=REPO)
            target = vm.condition(cid)
            if vm.record != REJECTED:
                return _fail(
                    f"c{cid} mutation survived record={vm.record} "
                    f"status={target.status} reason={target.reason}"
                )
            if target.status != FAIL:
                return _fail(
                    f"c{cid} not wired: record={vm.record} "
                    f"status={target.status} reason={target.reason}"
                )
            mutant_rows.append(
                {
                    "id": cid,
                    "record": vm.record,
                    "status": target.status,
                    "reason": target.reason,
                }
            )

        prov = S.materialize_provisional(root)
        vp = certify_workflow(prov, repo=REPO)
        if vp.record != PROVISIONAL:
            return _fail(f"provisional got {vp.record}")
        if vp.condition(9).status != UNKNOWN:
            return _fail(f"c9 expected UNKNOWN got {vp.condition(9).status}")

        xz = S.materialize_exit_zero_missing(root)
        vz = certify_workflow(xz, repo=REPO)
        if vz.record != REJECTED:
            return _fail(f"exit-zero-missing got {vz.record}")
        if vz.condition(2).status != FAIL:
            return _fail(f"exit-zero C2 not FAIL: {vz.condition(2).status}")
        if vz.notes.get("exit_only_rejected") is not True and vz.condition(2).status != FAIL:
            return _fail("exit-zero alone was treated as success")

        na = S.materialize_na_with_reason(root)
        vna = evaluate(na, locus="probe1-na", repo=REPO)
        if vna.condition(9).status != NA:
            return _fail(f"N/A not rendered: {vna.condition(9).status}")
        if vna.condition(9).status == PASS:
            return _fail("N/A counted as PASS")
        if vna.record != CERTIFIED:
            return _fail(f"N/A with others passing should CERTIFIED got {vna.record}")
        if vna.notes.get("na_count") != 1:
            return _fail(f"na_count={vna.notes.get('na_count')}")
        if vna.notes.get("pass_count") != 11:
            return _fail(f"pass_count should be 11 got {vna.notes.get('pass_count')}")

        bad_na = S.materialize_unreasoned_na(root)
        vbad = evaluate(bad_na, locus="probe1-unreasoned-na", repo=REPO)
        if vbad.record != REJECTED:
            return _fail(f"unreasoned N/A not fail-closed: {vbad.record}")
        if vbad.condition(9).status != FAIL:
            return _fail(f"unreasoned N/A c9={vbad.condition(9).status}")

    art_mut = (doc.get("mutation_control") or {}).get("per_condition") or []
    if len(art_mut) != 12:
        return _fail(f"artifact mutation_control rows={len(art_mut)}")
    live_ids = [r["id"] for r in mutant_rows]
    art_ids = [r.get("id") for r in art_mut]
    if live_ids != art_ids:
        return _fail(f"artifact mutation ids {art_ids} != live {live_ids}")
    for live, art in zip(mutant_rows, art_mut):
        if art.get("record") != REJECTED or art.get("status") != FAIL:
            return _fail(f"artifact mutation row not REJECTED/FAIL: {art}")
        if art.get("reason") != live["reason"]:
            return _fail(
                f"c{live['id']} reason artifact={art.get('reason')!r} "
                f"live={live['reason']!r}"
            )

    summary = {
        "ok": True,
        "probe": "probe1-mutation",
        "unit_id": "WFA-0134",
        "golden": CERTIFIED,
        "mutants_rejected": 12,
        "provisional": PROVISIONAL,
        "exit_zero_rejected": True,
        "na_never_pass": True,
        "unreasoned_na_fail_closed": True,
        "mutants": mutant_rows,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:WFA-0134-probe1 12/12 mutants REJECTED; golden CERTIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
