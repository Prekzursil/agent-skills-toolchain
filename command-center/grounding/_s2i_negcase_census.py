"""Census the description-quality axes on the REPO canonical root.

The brief quoted 261/328 WHEN, 69 negative, 46 sibling, 54 returns; the builder
measured 257/79/54 and the auditor 256/82/54 -- all three against the DEPLOYED
328-skill tree, not this repo's 346.  Rather than repeat a number I did not
take, this measures the tree the gate actually guards.

Detector control: a marker set that matches nothing would report 0 for every
axis and look like a finding.  So each axis prints a sample of matched names --
an all-zero axis with an empty sample is a broken matcher, not a clean fleet.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "_m", Path(__file__).with_name("_s2i_measure.py")
)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

WHEN = re.compile(r"\buse\s+(when|for|if|to)\b", re.I)
NEGATIVE = re.compile(r"\b(do\s*not|don't|never)\s+use\b|\bnot\s+for\b", re.I)
SIBLING = re.compile(r"\buse\s+(?:the\s+)?[`a-z0-9-]+\s+(?:skill\s+)?instead\b", re.I)
RETURNS = re.compile(r"\breturns?\b", re.I)

root = REPO / ".agents" / "skills"
rows = []
for path in sorted(root.glob("*/SKILL.md")):
    parsed = m.parse(path)
    if "error" not in parsed:
        rows.append(parsed)

axes = {
    "states WHEN to use": WHEN,
    "states a NEGATIVE case": NEGATIVE,
    "names the SIBLING to use instead": SIBLING,
    "says what it RETURNS": RETURNS,
}

print(f"canonical root: {len(rows)} skills")
for label, pattern in axes.items():
    hit = [r["name"] for r in rows if pattern.search(r["desc"])]
    sample = ", ".join(sorted(hit)[:3]) if hit else "<NONE -- matcher may be broken>"
    print(f"  {label:36s} {len(hit):4d}/{len(rows)}   e.g. {sample}")
