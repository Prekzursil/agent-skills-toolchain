"""Control for _d1 section C, which reported 4436 evidence strings and ZERO anchors.

That shape is self-contradicting on its face, and a self-contradicting output is a DETECTOR
failure, not a finding. Either the real registries genuinely carry no file:line anchors, or the
harvester is reading the wrong field. This prints the actual shape so the answer is read off the
data instead of inferred.

`git_show` is deliberately re-implemented here rather than imported from `_d1_anchor_corpus.py`
(the dup-guard hook flagged it, correctly, and this is the answer): _d2 is the CONTROL for _d1.
Importing _d1's reader would make the control inherit any defect in the thing it exists to
check -- two instruments sharing an input are one signal, not two. The first run of _d1 did in
fact carry a reader bug (a cp1252 decode that dropped files silently), which is precisely the
class this separation is here to catch.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CURRENT = re.compile(r"https?://\S+|\S+:\d+")

TARGETS = [
    "command-center/CLAIM-REGISTRY.json",
    "platform/corpus/CANONICAL-CLAIMS.json",
    "command-center/P11-CONFIRMATION.json",
    "command-center/adversarial/ADV-0005-p0-p1-fresh-context-rederivation.json",
]


def git_show(path: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout if proc.returncode == 0 else None


def main() -> int:
    for path in TARGETS:
        blob = git_show(path)
        print(f"== {path} ==")
        if blob is None:
            print("  NOT READABLE at HEAD")
            continue
        try:
            payload = json.loads(blob)
        except ValueError as exc:
            print(f"  UNPARSEABLE: {exc}")
            continue
        claims = payload.get("claims") if isinstance(payload, dict) else None
        if not isinstance(claims, list):
            print(
                f"  top-level keys: {sorted(payload)[:12] if isinstance(payload, dict) else type(payload)}"
            )
            print("  no top-level 'claims' LIST -> _d1 would skip this file entirely")
            continue
        print(f"  claims: {len(claims)}")
        keys = Counter()
        has_verdict = 0
        ev_types = Counter()
        anchored = 0
        samples = []
        for claim in claims:
            if not isinstance(claim, dict):
                ev_types["claim-not-dict"] += 1
                continue
            keys.update(claim.keys())
            if "verdict" in claim:
                has_verdict += 1
            ev = claim.get("evidence")
            ev_types[type(ev).__name__] += 1
            items = ev if isinstance(ev, list) else ([ev] if ev is not None else [])
            for item in items:
                if isinstance(item, str):
                    if CURRENT.search(item):
                        anchored += 1
                        if len(samples) < 4:
                            samples.append(item[:110])
                elif len(samples) < 4 and isinstance(item, dict):
                    samples.append(f"<dict keys={sorted(item)[:6]}>")
        print(f"  claims carrying 'verdict': {has_verdict}")
        print(f"  most common claim keys: {[k for k, _ in keys.most_common(10)]}")
        print(f"  evidence field types: {dict(ev_types)}")
        print(f"  evidence strings matching the CURRENT anchor rule: {anchored}")
        for s in samples:
            print(f"    sample: {s!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
