#!/usr/bin/env python3
"""Named probe 2: threshold-lowering mutation injects a weak match.

The no-fit corpus test is green at the production FIT_THRESHOLD. Lowering the
threshold so a weak overlap is injected as SELECTED must turn that same test
red. A detector that stays green on both states is a broken detector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = S.RECEIPT


def main() -> int:
    if not ART.is_file():
        print("FAILED:IMP-0396-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if S.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0396-probe2 sentinel absent")
        return 1

    n = S.load_nofit()
    caps = S.capabilities(n)
    queries = S.nofit_queries(n)
    control = n.threshold_mutation_control(caps, queries)
    print(
        f"production pass={control['production']['pass']} "
        f"n={control['production']['n']} fail={control['production']['n_fail']} "
        f"threshold={control['production']['threshold']}"
    )
    print(
        f"mutant pass={control['mutant']['pass']} "
        f"n={control['mutant']['n']} fail={control['mutant']['n_fail']} "
        f"injected={control['mutant']['injected_weak_matches']} "
        f"threshold={control['mutant']['threshold']}"
    )
    print(
        f"silent_on_good={control['silent_on_good_state']} "
        f"fired_on_bad={control['fired_on_bad_state']}"
    )
    if not control["silent_on_good_state"]:
        print("FAILED:IMP-0396-probe2 production no-fit corpus is not green")
        return 1
    if not control["fired_on_bad_state"]:
        print("FAILED:IMP-0396-probe2 lowering the threshold did not inject a weak match")
        return 1
    if control["mutant"]["pass"] is not False:
        print("FAILED:IMP-0396-probe2 mutant corpus test stayed green")
        return 1
    if control["mutant"]["injected_weak_matches"] < 1:
        print("FAILED:IMP-0396-probe2 no weak match was injected")
        return 1

    recorded = doc.get("threshold_mutation") or {}
    if recorded.get("fired_on_bad_state") is not True:
        print("FAILED:IMP-0396-probe2 receipt missing fired_on_bad_state")
        return 1
    if recorded.get("silent_on_good_state") is not True:
        print("FAILED:IMP-0396-probe2 receipt missing silent_on_good_state")
        return 1
    rec_n = int((recorded.get("mutant") or {}).get("injected_weak_matches") or 0)
    if rec_n != control["mutant"]["injected_weak_matches"]:
        print(
            "FAILED:IMP-0396-probe2 receipt injected count drift "
            f"{rec_n} != {control['mutant']['injected_weak_matches']}"
        )
        return 1

    sample = control["injected"][0]
    print(
        f"sample_injection query={sample['query']!r} "
        f"prod={sample['production_verdict']}@{sample['production_best']} "
        f"mut={sample['mutant_verdict']} {sample['mutant_selected']}@{sample['mutant_score']}"
    )
    print("SUCCESS:IMP-0396-probe2 threshold mutation injects weak match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
