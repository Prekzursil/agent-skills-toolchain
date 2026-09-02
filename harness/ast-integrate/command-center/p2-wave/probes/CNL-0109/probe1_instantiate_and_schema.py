#!/usr/bin/env python3
"""Probe 1: instantiate both family members; schema 0 on goods, >0 on mutant."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import family as F  # noqa: E402
import schema_check as S  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0109-strategy-and-constrained-prioritisation-family.md"


def _task(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0109-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0109" or "SUCCESS:CNL-0109" not in json.dumps(doc):
        print("FAILED:CNL-0109-probe1 sentinel/unit_id")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0109-probe1 self-declared", doc.get("state"))
        return 1

    live = [
        F.instantiate(_task("task_direction.json")),
        F.instantiate(_task("task_portfolio.json")),
    ]
    recorded = doc.get("instantiations") or []
    if len(recorded) != 2:
        print(f"FAILED:CNL-0109-probe1 instantiations={len(recorded)} want=2")
        return 1
    for got, want in zip(recorded, live):
        for key in (
            "task_id",
            "preset_id",
            "roster",
            "protocol_schedule",
            "voting_method",
            "stopping_expression",
        ):
            if got.get(key) != want.get(key):
                print(f"FAILED:CNL-0109-probe1 mismatch {key} {got.get(key)!r} vs {want.get(key)!r}")
                return 1
        print(
            f"instantiate task={got['task_id']} preset={got['preset_id']} "
            f"vote={got['voting_method']} stop={got['stopping_expression'][:48]}..."
        )

    if live[0]["voting_method"] == live[1]["voting_method"]:
        print("FAILED:CNL-0109-probe1 both members share a voting method")
        return 1
    if live[0]["preset_id"] == live[1]["preset_id"]:
        print("FAILED:CNL-0109-probe1 both tasks bound the same preset")
        return 1

    pval = S.preset_validator()
    valid_n = 0
    for preset in doc["presets"]:
        errs = S.error_messages(pval, preset)
        print(f"schema preset={preset['id']} errors={len(errs)}")
        valid_n += len(errs)
    if valid_n != 0:
        print("FAILED:CNL-0109-probe1 valid records not error-count 0")
        return 1

    mutant = S.ranked_choice_portfolio_mutant(doc["presets"][1])
    mutant_errs = S.error_messages(pval, mutant)
    print(f"schema mutant={mutant['id']} errors={len(mutant_errs)}")
    if not mutant_errs:
        print("FAILED:CNL-0109-probe1 mutant produced 0 errors (vacuous validator)")
        return 1
    verbatim = mutant_errs[0]
    recorded_nc = (doc.get("negative_control") or {}).get("verbatim") or ""
    if verbatim not in recorded_nc and recorded_nc not in verbatim:
        # Accept prefix match: artifact stores the first error string.
        if recorded_nc.split(":")[0] not in verbatim and verbatim not in recorded_nc:
            print("FAILED:CNL-0109-probe1 negative_control verbatim mismatch")
            print(" live:", verbatim)
            print(" art :", recorded_nc)
            return 1
    print("negative_control verbatim:", verbatim)

    owner_fired = False
    try:
        F.instantiate(
            _task("task_portfolio.json"),
            owner_overrides={"delta.voting.rule": "ranked-choice"},
        )
    except ValueError as exc:
        owner_fired = True
        print("owner_override rejected:", exc)
    if not owner_fired:
        print("FAILED:CNL-0109-probe1 owner override of voting.rule accepted")
        return 1

    fam_errs = S.error_messages(S.family_validator(), doc)
    print(f"schema family_doc errors={len(fam_errs)}")
    if fam_errs:
        print("\n".join(fam_errs[:12]))
        print("FAILED:CNL-0109-probe1 family document invalid")
        return 1

    print(
        "SUCCESS:CNL-0109-probe1 instantiate+schema "
        f"valid_errors=0 invalid_errors={len(mutant_errs)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
