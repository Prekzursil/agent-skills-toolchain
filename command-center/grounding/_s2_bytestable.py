"""Second, mechanically-independent byte-stability signal for the 4 cross-session flips.

mtime says "last write was at T". That is the correct semantics here (not the banned
"is it stalled" heuristic), but mtime is preserved by a copy and can be set, so it is
ONE signal. G-BARE-DESC.json recorded `size` per skill at the PRIOR observation --
a content-derived number written by a different probe at a different time. If size
AND mtime both agree the file did not change, the flip cannot be a file-content effect.

DETECTOR CONTROL: the same comparison is run over the WHOLE fleet, so the probe must
be able to FIND changed files. If it reports "0 changed" fleet-wide it is broken --
we know at least `writing-skills` was edited today.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

G = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/G-BARE-DESC.json"
)
DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")

prior = {r["name"]: r for r in json.loads(G.read_text(encoding="utf-8"))}
FLIPS = [
    "use-image-clipboard",
    "using-git-worktrees",
    "verification-before-completion",
    "writing-skills",
]

changed_fleet = []
for name, pr in prior.items():
    sk = DAILY / name / "SKILL.md"
    if not sk.exists():
        changed_fleet.append((name, "GONE"))
        continue
    st = sk.stat()
    if pr.get("size") != st.st_size or abs((pr.get("mtime") or 0) - st.st_mtime) > 1:
        changed_fleet.append((name, f"{pr.get('size')}->{st.st_size}"))

print("DETECTOR CONTROL -- the comparator must be able to see a change")
print(f"  fleet skills compared        : {len(prior)}")
print(f"  changed since prior snapshot : {len(changed_fleet)}")
for n, d in sorted(changed_fleet):
    print(f"     {n:44s} {d}")
if not changed_fleet:
    print("  -> 0 changed fleet-wide is IMPLAUSIBLE; comparator broken, probe void")

print()
print("THE 4 CROSS-SESSION FLIPS (described -> bare)")
print(f"  {'skill':38s} {'size then':>10s} {'size now':>9s} {'mtime now':>20s}  verdict")
for n in FLIPS:
    pr = prior.get(n, {})
    sk = DAILY / n / "SKILL.md"
    st = sk.stat()
    same = pr.get("size") == st.st_size and abs((pr.get("mtime") or 0) - st.st_mtime) <= 1
    print(
        f"  {n:38s} {pr.get('size', -1):10d} {st.st_size:9d} "
        f"{dt.datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M:%S}  "
        f"{'BYTE-STABLE -> H-PARSE refuted' if same else 'CHANGED -> confound, excluded'}"
    )
