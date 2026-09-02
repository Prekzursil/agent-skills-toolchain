#!/usr/bin/env python3
"""Named probe 1: disagreeing nested councils, averaging mutant, agree control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from experiment import run_experiment  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0095-council-of-councils-fanin.json"
SENTINEL = (
    "SUCCESS:CNF-0095 emitted only when the artifact at output_path exists, is non-empty, "
    "parses against output_schema, and the reducer invocation trace shows the same predicate "
    "at both levels and the tally arithmetic is attached. Any other terminal state is "
    "FAILED:CNF-0095 <classification> with the diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0095-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNF-0095-probe1 unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0095-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0095-probe1 sentinel-absent")
        return 1
    if not isinstance(doc.get("reducer_invocation_trace"), list) or len(doc["reducer_invocation_trace"]) < 2:
        print("FAILED:CNF-0095-probe1 reducer invocation trace missing")
        return 1
    if not isinstance(doc.get("parent_tally_arithmetic"), dict):
        print("FAILED:CNF-0095-probe1 tally arithmetic missing")
        return 1

    live = run_experiment()
    if live["disagree"]["verdict"] == "COMPLETE":
        print("FAILED:CNF-0095-probe1 parent averaged disagreement into COMPLETE")
        return 1
    if not live["disagreement_surfaced_not_averaged"]:
        print("FAILED:CNF-0095-probe1 disagreement not surfaced")
        print(json.dumps({k: live[k] for k in ("child_verdict_labels", "averaged_mutant")}, default=str)[:1500])
        return 1
    if live["averaged_mutant"]["verdict"] != "COMPLETE":
        print("FAILED:CNF-0095-probe1 averaging mutant did not fire (control inert)")
        return 1
    if not live["agree_completes_without_spurious_escalation"]:
        print("FAILED:CNF-0095-probe1 agreeing nesting did not complete")
        return 1
    if not live["flat_complete"]:
        print("FAILED:CNF-0095-probe1 flat complete case failed")
        return 1

    labels = live["child_verdict_labels"]
    print(
        json.dumps(
            {
                "parent_verdict": live["disagree"]["verdict"],
                "disagreement": live["disagree"]["disagreement"],
                "child_verdicts": labels,
                "averaging_mutant_verdict": live["averaged_mutant"]["verdict"],
                "agree_verdict": live["agree"]["verdict"],
                "computed_not_asserted": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"parent={live['disagree']['verdict']} disagreement={live['disagree']['disagreement']} "
        f"children={labels} mutant={live['averaged_mutant']['verdict']} agree={live['agree']['verdict']}"
    )
    print("SUCCESS:CNF-0095-probe1 nested disagreement surfaced, averaging mutant fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
