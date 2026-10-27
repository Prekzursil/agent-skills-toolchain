#!/usr/bin/env python3
"""TST-0236 probe 1: the retention gate exercises all three outcomes live.

Runs the production gate tools/selfimprove/retain.py:retain over tempfile
copies of fixtures/retain-estate (score.json value=5 + unrelated.txt):
  * win:      score 5 -> 10  => KEEP, measured-improvement, tree changes
  * neutral:  agent-produced rewrite, score stays 5 => REVERT/neutral,
              post-revert tree hash equals the pre-candidate hash
  * harmful:  score 5 -> 1 plus a new file => REVERT/harmful, full restore
Ledger is an append-only JSONL outside the hashed subject tree.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from selfimprove.retain import take_snapshot  # noqa: E402
from selfimprove import retain as retain_mod  # noqa: E402

FIXTURE = REPO / "tools" / "selfimprove" / "fixtures" / "retain-estate"


def fresh_tree(tmp: Path) -> Path:
    tree = tmp / "subject"
    shutil.copytree(FIXTURE, tree, dirs_exist_ok=True)
    return tree


def main() -> int:
    checks: dict[str, bool] = {}
    rows_out: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="tst0236-probe1-") as td:
        tmp = Path(td)
        ledger = tmp / "retain-ledger.jsonl"

        tree = fresh_tree(tmp)
        pre = take_snapshot(tree)
        win = retain_mod.retain(
            tree=tree,
            candidate_id="cand-win",
            files={"score.json": json.dumps({"value": 10})},
            ledger_path=ledger,
        )
        post = take_snapshot(tree)
        checks["win_kept"] = (
            win["decision"] == "KEEP"
            and win["reason"] == "measured-improvement"
            and win["before_score"] == 5.0
            and win["after_score"] == 10.0
            and win["hashes_equal"] is False
            and post.tree_hash != pre.tree_hash
        )
        rows_out["win"] = {
            "decision": win["decision"],
            "reason": win["reason"],
            "before_score": win["before_score"],
            "after_score": win["after_score"],
            "hashes_equal": win["hashes_equal"],
            "pre": pre.tree_hash,
            "post": post.tree_hash,
        }

        tree = fresh_tree(tmp)
        pre = take_snapshot(tree)
        neutral = retain_mod.retain(
            tree=tree,
            candidate_id="cand-neutral",
            files={
                "score.json": json.dumps({"value": 5}),
                "notes.md": "agent-produced rewrite; no measured change",
            },
            ledger_path=ledger,
            produced_by="agent",
        )
        post = take_snapshot(tree)
        checks["neutral_agent_reverted"] = (
            neutral["decision"] == "REVERT"
            and neutral["reason"] == "neutral"
            and neutral["hashes_equal"] is True
            and post.tree_hash == pre.tree_hash
        )
        checks["neutral_left_no_new_file"] = not (tree / "notes.md").exists()
        rows_out["neutral"] = {
            "decision": neutral["decision"],
            "reason": neutral["reason"],
            "hashes_equal": neutral["hashes_equal"],
            "produced_by": "agent",
            "pre": pre.tree_hash,
            "post": post.tree_hash,
        }

        tree = fresh_tree(tmp)
        pre = take_snapshot(tree)
        harmful = retain_mod.retain(
            tree=tree,
            candidate_id="cand-harmful",
            files={
                "score.json": json.dumps({"value": 1}),
                "extra.txt": "stray file a harmful candidate dragged in",
            },
            ledger_path=ledger,
        )
        post = take_snapshot(tree)
        checks["harmful_reverted"] = (
            harmful["decision"] == "REVERT"
            and harmful["reason"] == "harmful"
            and harmful["hashes_equal"] is True
            and post.tree_hash == pre.tree_hash
        )
        checks["harmful_left_no_stray_file"] = not (tree / "extra.txt").exists()
        rows_out["harmful"] = {
            "decision": harmful["decision"],
            "reason": harmful["reason"],
            "hashes_equal": harmful["hashes_equal"],
            "pre": pre.tree_hash,
            "post": post.tree_hash,
        }

        ledger_rows = retain_mod.read_ledger(ledger)
        checks["ledger_append_only_three_rows"] = len(ledger_rows) == 3
        checks["ledger_outside_subject_tree"] = not (tmp / "subject" / "retain-ledger.jsonl").exists()
        checks["ledger_decisions_recorded"] = [r["decision"] for r in ledger_rows] == [
            "KEEP",
            "REVERT",
            "REVERT",
        ]

    checks["fixture_score_json_value_5"] = (
        json.loads(FIXTURE.joinpath("score.json").read_text(encoding="utf-8")).get("value") == 5
    )
    checks["production_module_is_the_surface"] = (
        retain_mod.__file__ is not None
        and Path(retain_mod.__file__).resolve()
        == (REPO / "tools" / "selfimprove" / "retain.py").resolve()
    )
    out = {
        "probe": "probe1-three-outcomes",
        "unit_id": "TST-0236",
        "outcomes": rows_out,
        "ledger_rows": len(ledger_rows),
        "checks": checks,
        "pass": all(checks.values()),
    }
    (HERE / "probe1_three_outcomes.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
