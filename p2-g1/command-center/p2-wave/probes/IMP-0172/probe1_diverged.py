"""IMP-0172 probe 1 (source, the exact measured blind spot): a both-sides-unique
fixture is classified DIVERGED by the two-directional diff, never one-sided;
the one-directional mutant reports RIGHT-AHEAD on the same pair, dropping the
left-unique content; stripping the left-unique stage leaves DIVERGED.

Exit 0 iff all three states hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixtures import load_both_sides, pairs  # noqa: E402
import semantic_diff as SD  # noqa: E402

RAW = HERE / "probe1-diverged.raw.txt"

left, right = load_both_sides()
two = SD.diff_workflows(left, right)
one = SD.diff_workflows(left, right, one_directional=True)
lines = [json.dumps({"probe": "probe1-diverged", "unit_id": "IMP-0172",
                     "left_unique": two["left_unique"], "right_unique": two["right_unique"],
                     "ops": two["ops"],
                     "two_directional_verdict": two["verdict"],
                     "one_directional_verdict": one["verdict"]})]

assert two["verdict"] == "DIVERGED", f"both-sides-unique classified {two['verdict']}"
assert two["left_unique"] == 5 and two["right_unique"] == 5, (two["left_unique"], two["right_unique"])
assert one["verdict"] == "RIGHT-AHEAD", "one-directional mutant lost its counterexample value"

strip = json.loads(json.dumps(left))
strip["stages"] = [s for s in strip["stages"] if s["name"] != "adversarial-review"]
strip["roles"] = [r for r in strip["roles"] if r != "refuter"]
strip["gates"] = [g for g in strip["gates"] if g != "no-open-p0"]
strip["edges"] = [e for e in strip["edges"] if "adversarial-review" not in e]
stripped = SD.diff_workflows(strip, right)
lines.append(json.dumps({"both_states_stripped_left": {"verdict": stripped["verdict"]}}))
assert stripped["verdict"] == "RIGHT-AHEAD", "stripped-left state did not leave DIVERGED"

RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"two_directional": two["verdict"],
                              "one_directional_mutant": one["verdict"],
                              "left_unique": two["left_unique"],
                              "right_unique": two["right_unique"]}))
print("SUCCESS:IMP-0172-probe1 both-sides-unique classified DIVERGED")
