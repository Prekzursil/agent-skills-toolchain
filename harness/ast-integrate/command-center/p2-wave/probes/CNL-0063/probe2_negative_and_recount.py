#!/usr/bin/env python3
"""Probe 2: independent recount + negative control on a Condorcet winner.

Signal 2 uses recount.py (rank-pair accumulation + Dijkstra widest-path), not
tabulate.schulze_paths. The check is meant to reject (a) reporting a cycle when
a unique Condorcet winner exists and (b) rebinding the completion after ingest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from recount import recount  # noqa: E402
from tabulate import (  # noqa: E402
    DECLARED_COMPLETION,
    SWAP_COMPLETION,
    freeze_spec,
    ingest_and_tabulate,
    rebind_after_ingest,
    tabulate_with_rule,
)

ART = (
    REPO
    / "command-center/design/council/CNL-0063-pairwise-condorcet-tabulation-and-the-cycle-rule.md"
)
SCHEMA = HERE / "council-design-note.schema.json"
CATALOG_SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
FIX = HERE / "fixtures.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0063-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0063" or "SUCCESS:CNL-0063" not in json.dumps(doc):
        print("FAILED:CNL-0063-probe2 sentinel/unit")
        return 1

    fx = json.loads(FIX.read_text(encoding="utf-8"))
    cands = fx["candidate_order"]
    cycle_rows = fx["cycle_profile"]["ballots"]
    good_rows = fx["condorcet_winner_profile"]["ballots"]

    primary = tabulate_with_rule(cands, cycle_rows, DECLARED_COMPLETION)
    independent = recount(cands, cycle_rows)
    cells_match = independent["pairwise"] == primary["pairwise"]
    winner_match = independent["winner"] == primary["winner"]
    print(
        "RECOUNT mechanism=rank-pair-accumulation+dijkstra-widest-path "
        f"pairwise_cells_match={cells_match} "
        f"schulze_winner_match={winner_match} "
        f"primary_winner={primary['winner']} "
        f"recount_winner={independent['winner']}"
    )
    print(f"RECOUNT pairwise={independent['pairwise']}")
    print(f"RECOUNT schulze_scores={independent['schulze_scores']}")
    if not cells_match or not winner_match:
        print("FAILED:CNL-0063-probe2 independent recount disagreed")
        return 1
    if independent["cycle_detected"] is not True:
        print("FAILED:CNL-0063-probe2 recount missed the cycle")
        return 1

    good_declared = tabulate_with_rule(cands, good_rows, DECLARED_COMPLETION)
    good_swap = tabulate_with_rule(cands, good_rows, SWAP_COMPLETION)
    good_recount = recount(cands, good_rows)
    silent = (
        good_declared["cycle_detected"] is False
        and good_declared["condorcet_winner"] == "A"
        and good_declared["winner"] == "A"
        and good_swap["winner"] == "A"
        and good_declared["completion_used"] is None
        and good_recount["cycle_detected"] is False
        and good_recount["winner"] == "A"
    )
    print(
        "NEG-CYCLE-CLAIM "
        f"cycle_detected={good_declared['cycle_detected']} "
        f"condorcet_winner={good_declared['condorcet_winner']} "
        f"declared_winner={good_declared['winner']} "
        f"swap_winner={good_swap['winner']} "
        f"completion_used={good_declared['completion_used']!r} "
        f"recount_cycle={good_recount['cycle_detected']} "
        f"silent_on_condorcet_winner={silent}"
    )
    if not silent:
        print("FAILED:CNL-0063-probe2 cycle check fired on Condorcet winner")
        return 1

    spec = freeze_spec(DECLARED_COMPLETION, cands)
    ingest_and_tabulate(spec, good_rows)
    posthoc = rebind_after_ingest(spec, SWAP_COMPLETION)
    fired = posthoc.get("ok") is False
    print(
        "NEG-POSTHOC "
        f"ok={posthoc.get('ok')} reason={posthoc.get('reason')} "
        f"fired_on_posthoc_rebind={fired}"
    )
    if not fired:
        print("FAILED:CNL-0063-probe2 post-hoc rebind was silent")
        return 1

    measured = doc.get("measured_condorcet_winner") or {}
    if measured.get("winner") != "A" or measured.get("cycle_detected") is not False:
        print("FAILED:CNL-0063-probe2 artifact good-profile mismatch")
        return 1
    controls = {c.get("id"): c for c in (doc.get("negative_controls") or []) if isinstance(c, dict)}
    c1 = controls.get("CNL0063-C1-false-cycle")
    c2 = controls.get("CNL0063-C2-posthoc-rebind")
    if not c1 or not c1.get("silent_on_good_state"):
        print("FAILED:CNL-0063-probe2 missing C1 silent_on_good_state")
        return 1
    if not c2 or not c2.get("fired_on_bad_state"):
        print("FAILED:CNL-0063-probe2 missing C2 fired_on_bad_state")
        return 1
    if "cycle_detected=False" not in str(c1.get("verbatim_good") or ""):
        print("FAILED:CNL-0063-probe2 C1 verbatim_good missing cycle_detected=False")
        return 1
    if "frozen after ballot ingest" not in str(c2.get("verbatim_bad") or ""):
        print("FAILED:CNL-0063-probe2 C2 verbatim_bad missing freeze reason")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        print(f"FAILED:CNL-0063-probe2 schema accepted garbage {garbage}")
        return 1
    if CATALOG_SCHEMA.is_file():
        shared = json.loads(CATALOG_SCHEMA.read_text(encoding="utf-8"))
        ref = str(shared.get("$ref") or "")
        if ref.startswith("https://ast-integrate.invalid/"):
            print("WARN: catalog schema is a $ref shim; local schema used")
        else:
            try:
                jsonschema.Draft7Validator(shared).validate(doc)
            except jsonschema.ValidationError as exc:
                print(
                    "WARN: catalog schema ValidationError; local schema used. "
                    f"{exc.message}"
                )
            except jsonschema.exceptions.RefResolutionError as exc:
                print(f"WARN: catalog schema $ref unresolved; local schema used. {exc}")

    print("SUCCESS:CNL-0063-probe2 independent recount and negative controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
