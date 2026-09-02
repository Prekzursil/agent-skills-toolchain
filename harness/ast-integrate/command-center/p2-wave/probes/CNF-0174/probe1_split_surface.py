#!/usr/bin/env python3
"""Probe 1: construct the disagreement and observe fan-in.

Mechanically: run the confirmer-authored COMPLETE vs BLOCKED scenario through
fan_in, require the split to be surfaced with both verdicts and the minority
reason, require persistent-split escalation without looping, and require the
three-way reviewer construct to keep all three completions. Then check the
emitted confirmation record cites that fan-in output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fanin as F  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0174.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0174-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("confirmation artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0174":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:CNF-0174" not in json.dumps(doc):
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if not doc.get("source_probe"):
        return fail("empty source_probe")

    children = S.split_two()
    live = F.fan_in(children, split_detector=True, attempt=1)
    if live.get("averaged"):
        return fail("split was averaged")
    if not live.get("split_surfaced"):
        return fail("split_surfaced is false")
    if live.get("parent_verdict") != "SPLIT":
        return fail(f"parent_verdict={live.get('parent_verdict')} want SPLIT")
    if live.get("parent_completion") == "COMPLETE":
        return fail("parent COMPLETE despite split")
    completions = {r["id"]: r["completion"] for r in live["subcouncil_verdicts"]}
    if completions.get("sub-alpha") != "COMPLETE" or completions.get("sub-beta") != "BLOCKED":
        return fail(f"verbatim verdicts lost {completions}")
    if not any(r.get("reasoning") == S.BLOCKED_REASON for r in live["minority_reports"]):
        return fail("beta reasoning missing from parent minority_reports")
    if live.get("tally", {}).get("double_counted"):
        return fail("double-counted sources")
    if live.get("reducer_module") != "command-center/p2-wave/probes/CNF-0174/reducer.py":
        return fail("parent did not cite shared reducer module")
    if not live.get("escalation_path"):
        return fail("escalation_path empty")

    term = F.fan_in_until_terminal(S.persistent_split(), split_detector=True)
    if term.get("looped") or term.get("hit_safety_cap"):
        return fail("persistent split looped")
    if term.get("escalation") != F.ESCALATION_POLICY["on_persistent_split"]:
        return fail(f"escalation={term.get('escalation')}")
    if (term.get("history_attempts") or 0) > F.ESCALATION_POLICY["max_attempts"]:
        return fail("more attempts than policy allows")

    three = F.fan_in(S.three_way(), split_detector=True, attempt=1)
    three_c = {r["completion"] for r in three["subcouncil_verdicts"]}
    if not three.get("split_surfaced") or three_c != {"COMPLETE", "BLOCKED", "INCOMPLETE"}:
        return fail(f"three-way collapsed {three_c}")
    gamma = next(r for r in three["subcouncil_verdicts"] if r["id"] == "sub-gamma")
    if gamma["completion"] == "COMPLETE":
        return fail("gamma exit-zero-missing-artifact was treated COMPLETE")

    cited = doc.get("fan_in_output", {}).get("split") or {}
    if cited.get("parent_verdict") != "SPLIT" or not cited.get("split_surfaced"):
        return fail("artifact fan_in_output.split does not show the split")
    cited_ids = {r["id"]: r["completion"] for r in cited.get("subcouncil_verdicts") or []}
    if cited_ids != completions:
        return fail(f"artifact verdicts {cited_ids} != live {completions}")

    payload = {
        "adjudicated": "split-surfaced",
        "parent_verdict": live["parent_verdict"],
        "subcouncil_verdicts": completions,
        "minority_preserved": True,
        "escalation_path": live["escalation_path"],
        "persistent_escalation": term["escalation"],
        "three_way": sorted(three_c),
        "pass": True,
        "probe": "probe1-split-surface",
        "unit_id": "CNF-0174",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"split_surfaced={live['split_surfaced']} minority=True "
        f"escalation={term['escalation']} three_way={sorted(three_c)}"
    )
    print("SUCCESS:CNF-0174-probe1 split surfaced, minority preserved, deadlock escalated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
