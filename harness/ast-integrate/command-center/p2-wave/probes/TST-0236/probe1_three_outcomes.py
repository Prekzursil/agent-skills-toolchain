#!/usr/bin/env python3
"""Named probe 1: win KEEP, neutral REVERT, harmful REVERT, with tree hashes."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from selfimprove.retain import (  # noqa: E402
    measure_score_json,
    read_ledger,
    retain,
    tree_hash,
)

ESTATE = TOOLS / "selfimprove" / "fixtures" / "retain-estate"

WIN = {"score.json": json.dumps({"value": 10}, indent=2) + "\n"}
NEUTRAL = {
    "score.json": json.dumps({"value": 5, "agent": "produced this"}, indent=2) + "\n"
}
HARMFUL = {
    "score.json": json.dumps({"value": 1}, indent=2) + "\n",
    "extra.txt": "side-effect\n",
}


def fail(msg: str) -> int:
    print(f"FAILED:TST-0236-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0236-p1-") as raw:
        tmp = Path(raw)
        tree = tmp / "subject"
        shutil.copytree(ESTATE, tree)
        ledger = tmp / "retention-ledger.jsonl"
        unrelated = (tree / "unrelated.txt").read_bytes()

        win = retain(
            tree=tree,
            candidate_id="win",
            files=WIN,
            ledger_path=ledger,
            program_root=REPO,
        )
        if win.get("decision") != "KEEP" or win.get("reason") != "measured-improvement":
            return fail(f"win not kept: {win}")
        if win.get("before_score") != 5.0 or win.get("after_score") != 10.0:
            return fail(f"win scores wrong: {win}")
        if win.get("hashes_equal") or win["pre_tree_hash"] == win["post_decision_tree_hash"]:
            return fail("KEEP left the tree hash unchanged")
        if tree_hash(tree) != win["post_decision_tree_hash"]:
            return fail("live hash after KEEP does not match the recorded post hash")
        if measure_score_json(tree) != 10.0:
            return fail("KEEP did not retain the improved score.json")

        # Reset the subject so each outcome is exercised from the same baseline.
        shutil.rmtree(tree)
        shutil.copytree(ESTATE, tree)
        pre_neutral = tree_hash(tree)
        neutral = retain(
            tree=tree,
            candidate_id="neutral-agent",
            files=NEUTRAL,
            produced_by="agent",
            ledger_path=ledger,
            program_root=REPO,
        )
        if neutral.get("decision") != "REVERT" or neutral.get("reason") != "neutral":
            return fail(f"neutral was not reverted: {neutral}")
        if not neutral.get("hashes_equal"):
            return fail("neutral revert hashes_equal is false")
        if tree_hash(tree) != pre_neutral:
            return fail("neutral post-revert tree hash != pre-candidate hash")
        if tree_hash(tree) != neutral["post_decision_tree_hash"]:
            return fail("neutral live hash mismatch vs record")
        if "agent" in (tree / "score.json").read_text(encoding="utf-8"):
            return fail("agent-produced marker survived the revert")
        if measure_score_json(tree) != 5.0:
            return fail("neutral revert did not restore the baseline score")

        shutil.rmtree(tree)
        shutil.copytree(ESTATE, tree)
        pre_harm = tree_hash(tree)
        harm = retain(
            tree=tree,
            candidate_id="harm",
            files=HARMFUL,
            ledger_path=ledger,
            program_root=REPO,
        )
        if harm.get("decision") != "REVERT" or harm.get("reason") != "harmful":
            return fail(f"harmful was not reverted: {harm}")
        if not harm.get("hashes_equal"):
            return fail("harmful revert hashes_equal is false")
        if tree_hash(tree) != pre_harm:
            return fail("harmful post-revert tree hash != pre-candidate hash")
        if (tree / "extra.txt").exists():
            return fail("harmful candidate's extra.txt survived the revert")
        if (tree / "unrelated.txt").read_bytes() != unrelated:
            return fail("unrelated.txt was mutated")

        rows = read_ledger(ledger)
        decisions = [r.get("decision") for r in rows]
        reasons = [r.get("reason") for r in rows]
        if decisions != ["KEEP", "REVERT", "REVERT"]:
            return fail(f"ledger decisions {decisions}")
        if reasons != ["measured-improvement", "neutral", "harmful"]:
            return fail(f"ledger reasons {reasons}")

        payload = {
            "probe": "probe1-three-outcomes",
            "unit_id": "TST-0236",
            "win": {
                "decision": win["decision"],
                "reason": win["reason"],
                "pre": win["pre_tree_hash"],
                "post": win["post_decision_tree_hash"],
                "hashes_equal": win["hashes_equal"],
                "before_score": win["before_score"],
                "after_score": win["after_score"],
            },
            "neutral": {
                "decision": neutral["decision"],
                "reason": neutral["reason"],
                "pre": neutral["pre_tree_hash"],
                "post": neutral["post_decision_tree_hash"],
                "hashes_equal": neutral["hashes_equal"],
                "produced_by": "agent",
            },
            "harmful": {
                "decision": harm["decision"],
                "reason": harm["reason"],
                "pre": harm["pre_tree_hash"],
                "post": harm["post_decision_tree_hash"],
                "hashes_equal": harm["hashes_equal"],
            },
            "ledger_rows": len(rows),
            "pass": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            "win=KEEP neutral=REVERT harmful=REVERT "
            "neutral_hash_restored=True harmful_hash_restored=True"
        )
        print("SUCCESS:TST-0236-probe1 three outcomes; revert proven by tree hash")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
