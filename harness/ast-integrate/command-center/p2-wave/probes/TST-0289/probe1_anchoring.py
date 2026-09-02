#!/usr/bin/env python3
"""Probe 1: matched revealed vs concealed councils, n>=20, with intervals."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import experiment as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0289.json"
UID = "TST-0289"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0289-probe1 {msg}")
    return 1


def main() -> int:
    exp = E.run_experiment()
    missing = E.loud_missing_persona()
    print(
        json.dumps(
            {
                "probe": "probe1-anchoring-matched-councils",
                "unit_id": UID,
                "n_pairs": exp["n_pairs"],
                "finding": exp["finding"],
                "independence_delta": exp["independence_delta"],
                "independence_cohens_dz": exp["independence_cohens_dz"],
                "pull_delta": exp["pull_delta"],
                "pull_cohens_dz": exp["pull_cohens_dz"],
                "verdict_disagree_rate": exp["verdict_disagree_rate"],
                "ceremony_independence_delta": exp["ceremony_independence_delta"],
                "ceremony_independence_compatible_with_null": exp[
                    "ceremony_independence_compatible_with_null"
                ],
                "controls": exp["controls"],
                "missing_persona": missing,
            },
            indent=2,
            sort_keys=True,
        )
    )

    if exp["n_pairs"] < 20:
        return fail(f"n_pairs {exp['n_pairs']} < 20")
    if "persona-missing:" not in missing:
        return fail(f"corrupt persona was silent: {missing!r}")
    ctl = exp["controls"]
    if not ctl["same_seed_hash_ok"]:
        return fail("same-seed transcript hash not stable")
    if not ctl["different_seed_hash_ok"]:
        return fail("seed is not wired; hashes identical across seeds")
    if not ctl["high_status_first_all_revealed"]:
        return fail("revealed arm did not seat high-status first speaker P")
    if ctl["names_leaked_concealed"]:
        return fail("concealed openings still carry real names")
    if ctl["tool_traces_leaked_concealed"]:
        return fail("concealed openings still carry tool traces")
    if not exp["ceremony_independence_compatible_with_null"]:
        return fail("ceremony mask-only moved independence; control is not ceremony")
    for key in ("independence_delta", "pull_delta", "verdict_disagree_rate"):
        ci = exp[key]
        if "lo" not in ci or "hi" not in ci or "mean" not in ci:
            return fail(f"{key} missing interval")
        if int(ci.get("n") or 0) < 20:
            return fail(f"{key} n<20")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:TST-0289" not in text:
        return fail("sentinel-absent")
    if str(doc.get("finding") or "") != str(exp["finding"]):
        return fail("receipt finding does not match live experiment")

    print(
        f"n={exp['n_pairs']} finding={exp['finding']} "
        f"ind_mean={exp['independence_delta']['mean']:.6f} "
        f"pull_mean={exp['pull_delta']['mean']:.6f} "
        f"disagree={exp['verdict_disagree_rate']['mean']:.6f}"
    )
    print("SUCCESS:TST-0289-probe1 matched councils anchoring and independence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
