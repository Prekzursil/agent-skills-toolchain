"""IMP-0172 probe 2 (verifier, computed antisymmetry): for every fixture pair,
reverse(diff(a, b)) equals diff(b, a) - ops swapped, uniques swapped, verdicts
mirrored. Run over the full 8-pair matrix.

Exit 0 iff 8/8 pairs are antisymmetric.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixtures import pairs  # noqa: E402
import semantic_diff as SD  # noqa: E402

RAW = HERE / "probe2-antisymmetry.raw.txt"

lines, passed = [], 0
for name, a, b in pairs():
    ab = SD.diff_workflows(a, b)
    ba = SD.diff_workflows(b, a)
    rev = SD.reverse_diff(ab)
    ok = (rev["verdict"] == ba["verdict"]
          and rev["left_unique"] == ba["left_unique"]
          and rev["right_unique"] == ba["right_unique"]
          and sorted(rev["ops"]) == sorted(ba["ops"]))
    lines.append(f"ok pair={name} verdict={ab['verdict']} reverse={rev['verdict']} "
                 f"antisymmetric={str(ok).lower()}")
    assert ok, f"antisymmetry broken on pair {name}: {rev} vs {ba}"
    passed += 1

lines.append(json.dumps({"probe": "probe2-antisymmetry", "unit_id": "IMP-0172",
                         "pairs": len(pairs()), "passed": passed, "failed": []}))
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"pairs": len(pairs()), "passed": passed, "failed": []}))
print(f"SUCCESS:IMP-0172-probe2 antisymmetry holds on {passed}/{len(pairs())} fixture pairs")
