"""Targeted fix: IMP-0369 (fishbowl topology) shipped without a negative control.

Caught by _verify_imp3.py's per-unit assertion, not by eye. Adds a real negative control
rather than a word that satisfies the checker: the control must be capable of returning
an unflattering verdict about the mechanism itself.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "IMP-3.json")
data = json.loads(io.open(SRC, encoding="utf-8").read())
hit = 0
for u in data:
    if u["id"] == "IMP-0369":
        assert "fishbowl" in u["title"].lower(), u["title"]
        u["tests_required"].append(
            "negative control: re-run the same councils with the outer ring REMOVED; if the "
            "decision set is unchanged, report the fishbowl as cost-only rather than tuning the "
            "contribution metric until it looks useful")
        hit += 1
assert hit == 1, hit
with io.open(SRC, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=True)
    fh.write("\n")
print("patched IMP-0369, n=%d" % len(data))
