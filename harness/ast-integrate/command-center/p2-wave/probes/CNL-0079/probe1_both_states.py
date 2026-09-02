#!/usr/bin/env python3
"""Probe 1: A10 parse-unchanged, both-states stop, planted lexical-identity mutant."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from a10 import accepted_unchanged, parse_all_required, tautology_or_unsat_rejected
from evaluate import lexical_mutant_run, run_council
from expr import SPEC_LINE, SPEC_EXPRESSION
from fixtures import fire, silent_low_consensus, silent_new_objection
from identity import jaccard


def main() -> int:
    if not accepted_unchanged(SPEC_EXPRESSION):
        print("FAILED:CNL-0079-probe1 spec expression not accepted unchanged")
        return 1
    print(f"parse_unchanged=True expr={SPEC_EXPRESSION!r} anchor={SPEC_LINE}")

    rows = parse_all_required()
    for row in rows:
        ok = row.get("accepted_unchanged", row.get("accepted_unchanged"))
        print(f"a10_example accepted={ok} {row['expression']}")
        if not ok:
            print(f"FAILED:CNL-0079-probe1 a10 parse {row}")
            return 1

    unsat = tautology_or_unsat_rejected()
    print(f"unsat_control {json.dumps(unsat, sort_keys=True)}")
    unsat_flag = unsat.get("statically_unsatisfiable", unsat.get("statically_unsatisfiable"))
    ever = unsat.get("ever_true", unsat.get("ever_true"))
    if not unsat_flag or ever:
        print("FAILED:CNL-0079-probe1 grammar is vacuous")
        return 1

    f_true = fire()
    f_reset = silent_new_objection()
    f_low = silent_low_consensus()
    r_true = run_council(f_true)
    r_reset = run_council(f_reset)
    r_low = run_council(f_low)

    print(
        "true_fixture stop={stop} consensus={c:.4f} quiet={q} rounds={n}".format(
            stop=r_true["stop"],
            c=float(r_true["final"]["consensus"]),
            q=int(r_true["final"]["no_new_objection_rounds"]),
            n=len(r_true["rounds"]),
        )
    )
    print(
        "false_reset stop={stop} consensus={c:.4f} quiet={q} new_r3={n}".format(
            stop=r_reset["stop"],
            c=float(r_reset["final"]["consensus"]),
            q=int(r_reset["final"]["no_new_objection_rounds"]),
            n=r_reset["rounds"][-1]["new_count"],
        )
    )
    print(
        "false_low_consensus stop={stop} consensus={c:.4f} quiet={q}".format(
            stop=r_low["stop"],
            c=float(r_low["final"]["consensus"]),
            q=int(r_low["final"]["no_new_objection_rounds"]),
        )
    )

    if not r_true["stop"]:
        print("FAILED:CNL-0079-probe1 detector silent on true fixture")
        return 1
    if r_reset["stop"] or r_low["stop"]:
        print("FAILED:CNL-0079-probe1 detector fired on false fixture")
        return 1
    if int(r_true["final"]["no_new_objection_rounds"]) < 2:
        print("FAILED:CNL-0079-probe1 true fixture quiet rounds < 2")
        return 1
    if int(r_reset["final"]["no_new_objection_rounds"]) != 0:
        print("FAILED:CNL-0079-probe1 new-recruit new-objection did not reset")
        return 1
    recruit = r_true["rounds"][-1]["newly_recruited"]
    if recruit != ["R-new"]:
        print(f"FAILED:CNL-0079-probe1 fire fixture missing new recruit {recruit!r}")
        return 1
    if r_true["rounds"][-1]["new_count"] != 0:
        print("FAILED:CNL-0079-probe1 restatement from new recruit counted as new")
        return 1

    t0 = f_true["rounds"][0]["objections"][0]["text"]
    t1 = f_true["rounds"][1]["objections"][0]["text"]
    jac = jaccard(t0, t1)
    print(f"paraphrase_jaccard={jac:.4f} (lexical mutant threshold 0.85)")
    if jac >= 0.85:
        print("FAILED:CNL-0079-probe1 paraphrase Jaccard too high; fixture not planted-bad")
        return 1

    mutant = lexical_mutant_run(f_true)
    print(
        "planted_bad_lexical_mutant stop={stop} quiet={q} identity={id}".format(
            stop=mutant["stop"],
            q=int(mutant["final"].get("no_new_objection_rounds") or 0),
            id=mutant["identity"],
        )
    )
    if mutant["stop"]:
        print("FAILED:CNL-0079-probe1 lexical mutant must stay SILENT on paraphrase-true fixture")
        return 1
    print(
        "both_states expression FIRE on true, SILENT on false; "
        "identity-control FIRE (canonical stop) vs SILENT (lexical mutant on same true fixture)"
    )
    print("SUCCESS:CNL-0079-probe1 both-states parse planted-bad")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
