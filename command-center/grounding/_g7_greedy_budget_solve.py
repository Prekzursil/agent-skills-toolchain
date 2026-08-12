"""Test H-D: the skill listing renders descriptions by GREEDY BUDGET FILL, not a hard cut.

Model: walk the 328 skills in alphabetical (render) order, keeping `used`.
  if used + cost(entry) <= B:  render the description, used += cost(entry)
  else:                        render the NAME ONLY, used unchanged, KEEP GOING

A hard cut cannot produce an interleaved bare/described tail. Greedy fill can:
once the budget is nearly full, a SHORT description still fits while a LONG one
does not -- which is exactly the observed pattern (ui-drive 946 bare, the very next
skill ui-ux-pro-max 353 described).

FALSIFIABLE: solve for B. If NO value of B reproduces the observed 26-bare /
302-described partition exactly, H-D is REFUTED. Reported as mismatch count.

DETECTOR CONTROL: also score a HARD-CUT model over the same B sweep. The hard-cut
model must score strictly WORSE, otherwise the scorer cannot tell the two apart
and its verdict on H-D means nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/G-BARE-DESC.json"
)
rows = json.loads(DATA.read_text(encoding="utf-8"))

BARE = {
    "ui-drive",
    "ui-invariant-walk",
    "vercel-deploy",
    "verification-loop",
    "video-convert",
    "video-join-concat",
    "video-resize-aspect",
    "video-stabilize",
    "voice-analyze",
    "voice-apply",
    "voice-blend",
    "voice-create",
    "volatility-3",
    "webapp-testing",
    "windbg-command-cookbook",
    "windbg-preview",
    "windows-virtualization-conflict-triage",
    "winui-app",
    "workflow-foundry",
    "workflow-monitor",
    "writing-plans",
    "wsl-vmware-cutover",
    "x-api",
    "x64dbg",
    "yeet",
    "zero-issue-coding",
}

rows = [r for r in rows if r.get("desc_chars") is not None]
rows.sort(key=lambda r: r["name"])
observed = {r["name"]: (r["name"] in BARE) for r in rows}


def simulate(model: str, B: int, overhead: int) -> int:
    """Return count of skills whose predicted bare-ness differs from observed."""
    used = 0
    stopped = False
    wrong = 0
    for r in rows:
        cost = r["desc_chars"] + len(r["name"]) + overhead
        if model == "greedy":
            fits = used + cost <= B
            if fits:
                used += cost
            pred_bare = not fits
        else:  # hardcut: once it does not fit, everything after is bare
            if stopped:
                pred_bare = True
            else:
                fits = used + cost <= B
                if fits:
                    used += cost
                    pred_bare = False
                else:
                    stopped = True
                    pred_bare = True
        if pred_bare != observed[r["name"]]:
            wrong += 1
    return wrong


best = {}
for model in ("greedy", "hardcut"):
    for overhead in (0, 3, 4, 6):
        bb, bw = None, 10**9
        # sweep B over the plausible range around the observed 102k-115k cut
        for B in range(95_000, 125_001, 1):
            w = simulate(model, B, overhead)
            if w < bw:
                bw, bb = w, B
            if bw == 0:
                break
        best[(model, overhead)] = (bb, bw)
        print(f"{model:8s} overhead={overhead}: best B={bb} mismatches={bw}")

print()
gm = min(w for (m, _), (_, w) in best.items() if m == "greedy")
hm = min(w for (m, _), (_, w) in best.items() if m == "hardcut")
print(f"BEST greedy mismatches  = {gm}")
print(f"BEST hardcut mismatches = {hm}   (DETECTOR CONTROL: must be worse than greedy)")
if gm == 0:
    print(
        "VERDICT: H-D CONFIRMED -- greedy budget fill reproduces the partition EXACTLY."
    )
elif gm < hm:
    print(
        "VERDICT: H-D favoured but NOT exact -- greedy beats hard-cut but does not fit perfectly."
    )
else:
    print("VERDICT: H-D REFUTED -- greedy is no better than hard-cut.")

# Show the exact residual mismatches for the best greedy fit
(bb, bw) = (
    min(((v, k) for k, v in best.items() if k[0] == "greedy"), key=lambda t: t[0][1])[
        0
    ],
    None,
)
for (m, oh), (B, w) in best.items():
    if m == "greedy" and w == gm:
        used = 0
        print(f"\nRESIDUAL MISMATCHES for greedy B={B} overhead={oh}:")
        for r in rows:
            cost = r["desc_chars"] + len(r["name"]) + oh
            fits = used + cost <= B
            if fits:
                used += cost
            pred_bare = not fits
            if pred_bare != observed[r["name"]]:
                print(
                    f"   {r['name']:42s} desc={r['desc_chars']:5d} "
                    f"predicted={'BARE' if pred_bare else 'DESC'} "
                    f"observed={'BARE' if observed[r['name']] else 'DESC'}"
                )
        print(f"   final used={used} of B={B}")
        break
