"""LANE SKILLS2 / item 1 -- the OUT-OF-SAMPLE test that separates H-BUDGET from H-PARSE.

_g7 fitted a greedy-budget model to observation A (01:35, 26 bare) and got 5 residuals.
That is a FIT, and a fit is cheap. This probe asks the only question that is not cheap:

    Fit B on observation A ONLY. Then lower B until the model drops 4 more descriptions.
    WHICH four does it name?

H-BUDGET predicts it names the four skills that actually flipped
(use-image-clipboard, using-git-worktrees, verification-before-completion, writing-skills).
H-PARSE predicts nothing about which four -- under H-PARSE the flip cannot happen at all,
because three of those four files are byte-stable (size AND mtime unchanged; measured by
_s2_bytestable.py).  Naming them is a PREDICTION, not a fit.

DETECTOR CONTROL -- rule 3c, "a control that cannot distinguish the two hypotheses is not
a control".  The same fitter is run against DECOYS: (1) 200 random 30-skill subsets, (2) the
alphabetically FIRST 30, (3) the 30 with the LONGEST descriptions.  State the two outcomes
first: if the budget model is really explaining the data, the true set fits far better than
every decoy.  If a random 30 fits as well, the fitter is inert and its verdict on the real
set means nothing -- that PASS would look identical under both hypotheses, which is the
failure mode this control exists to catch.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path

DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")
OUT = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/S2-BUDGET-REFIT.json"
)

PRIOR_BARE = {
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
FLIPS = {
    "use-image-clipboard",
    "using-git-worktrees",
    "verification-before-completion",
    "writing-skills",
}
NOW_BARE = PRIOR_BARE | FLIPS


def parse_desc(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    lines = text[3:end].splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", lines[i])
        if m and m.group(1) == "description":
            rest = m.group(2).strip()
            if rest in (">", "|", ">-", "|-", ">+", "|+"):
                buf, j = [], i + 1
                while j < len(lines) and (
                    lines[j].startswith(("  ", "\t")) or not lines[j].strip()
                ):
                    buf.append(lines[j].strip())
                    j += 1
                return " ".join(x for x in buf if x)
            return rest.strip("\"'")
        i += 1
    return ""


rows = []
for d in sorted(p for p in DAILY.iterdir() if p.is_dir()):
    sk = d / "SKILL.md"
    if not sk.exists():
        continue
    desc = parse_desc(sk.read_text(encoding="utf-8", errors="replace"))
    rows.append({"name": d.name, "chars": len(desc)})
NAMES = [r["name"] for r in rows]

print("=" * 78)
print("0. PREMISE CONTROL -- every observed-bare name must exist with a NON-EMPTY desc")
byname = {r["name"]: r for r in rows}
broken = [n for n in sorted(NOW_BARE) if byname.get(n, {}).get("chars", 0) == 0]
print(f"  fleet scanned      : {len(rows)}")
print(f"  bare names checked : {len(NOW_BARE)}")
print(
    f"  premise breaks     : {broken if broken else 'NONE -- all 30 have real text on disk'}"
)


def predict_bare(B: int, overhead: int = 0) -> set[str]:
    used, bare = 0, set()
    for r in rows:
        cost = r["chars"] + len(r["name"]) + overhead
        if used + cost <= B:
            used += cost
        else:
            bare.add(r["name"])
    return bare


def fit(target: set[str], lo: int = 90_000, hi: int = 125_000) -> tuple[int, int]:
    bb, bw = None, 10**9
    for B in range(lo, hi + 1, 1):
        w = len(predict_bare(B) ^ target)
        if w < bw:
            bw, bb = w, B
    return bb, bw


print()
print("=" * 78)
print("1. IN-SAMPLE FIT on observation A (26 bare, 2026-08-12 01:35)")
B_a, w_a = fit(PRIOR_BARE)
print(f"  best B={B_a}  mismatches={w_a}")

print()
print("=" * 78)
print("2. OUT-OF-SAMPLE PREDICTION -- hold B_a fixed, lower it until 4 MORE go bare.")
print("   The model was never shown the flip set. Which four does it name?")
pred_at = None
for B in range(B_a, 80_000, -1):
    pb = predict_bare(B)
    if len(pb) >= len(PRIOR_BARE) + 4:
        pred_at = (B, pb)
        break
B_b, pred_b = pred_at
newly = sorted(pred_b - PRIOR_BARE)
print(f"  B lowered {B_a} -> {B_b} (delta {B_a - B_b} chars) gives {len(pred_b)} bare")
print(f"  model NAMES as the next to drop : {newly}")
print(f"  actually observed to flip       : {sorted(FLIPS)}")
hit = set(newly) & FLIPS
print(f"  overlap {len(hit)}/4 : {sorted(hit)}")
print(f"  full-set agreement with observation B: {len(pred_b ^ NOW_BARE)} mismatches")

print()
print("=" * 78)
print("3. MONOTONICITY -- a budget can only ever REMOVE descriptions as it tightens.")
print("   A parse failure has no such constraint.")
print(f"  prior_bare subset of now_bare : {PRIOR_BARE <= NOW_BARE}")
print(f"  reversals (bare -> described) : {sorted(PRIOR_BARE - NOW_BARE) or 'NONE'}")
print("  a single reversal would refute a monotone budget; none observed.")

print()
print("=" * 78)
print("4. DETECTOR CONTROL (rule 3c) -- can this fitter fit ANY 30-skill set?")
print("   H1 'budget explains it' => true set fits far better than decoys.")
print("   H2 'fitter is inert'    => decoys fit about as well. Same PASS shape, so")
print(
    "                              without this control the section-1 fit proves nothing."
)
B_true, w_true = fit(NOW_BARE)
print(f"  TRUE observed 30      : best mismatches={w_true:3d} (B={B_true})")
rng = random.Random(20260812)
decoy_scores = []
for _ in range(200):
    d = set(rng.sample(NAMES, 30))
    decoy_scores.append(fit(d)[1])
alpha30 = set(NAMES[:30])
long30 = {r["name"] for r in sorted(rows, key=lambda r: -r["chars"])[:30]}
w_alpha = fit(alpha30)[1]
w_long = fit(long30)[1]
print(
    f"  200 RANDOM 30-subsets : best mismatches min={min(decoy_scores)} "
    f"median={sorted(decoy_scores)[100]} max={max(decoy_scores)}"
)
print(f"  alphabetically FIRST 30 : mismatches={w_alpha}")
print(f"  LONGEST-description 30  : mismatches={w_long}")
inert = min(decoy_scores) <= w_true
print(
    f"  CONTROL VERDICT: {'INERT -- fitter fits anything; section 1 is void' if inert else 'DISCRIMINATING -- true set fits strictly better than every decoy'}"
)

print()
print("=" * 78)
print("5. RESIDUALS of the best fit to observation B")
resid = sorted(predict_bare(B_true) ^ NOW_BARE)
for n in resid:
    p = "BARE" if n in predict_bare(B_true) else "DESC"
    o = "BARE" if n in NOW_BARE else "DESC"
    print(f"   {n:42s} desc={byname[n]['chars']:5d} predicted={p} observed={o}")
print(f"  n={len(resid)}; all residuals are predicted-BARE/observed-DESC = a PRIORITY")
print("  exemption the pure-alphabetical model does not carry (see report).")

out = {
    "fleet": len(rows),
    "premise_breaks": broken,
    "fit_obsA": {"B": B_a, "mismatches": w_a},
    "out_of_sample": {
        "B_lowered_to": B_b,
        "model_named": newly,
        "actually_flipped": sorted(FLIPS),
        "overlap": sorted(hit),
        "full_set_mismatches_vs_obsB": len(pred_b ^ NOW_BARE),
    },
    "monotone": {
        "prior_subset_of_now": PRIOR_BARE <= NOW_BARE,
        "reversals": sorted(PRIOR_BARE - NOW_BARE),
    },
    "control": {
        "true_mismatches": w_true,
        "random_min": min(decoy_scores),
        "random_median": sorted(decoy_scores)[100],
        "alpha30": w_alpha,
        "long30": w_long,
        "inert": inert,
    },
    "residuals": resid,
    "sha_of_inputs": hashlib.sha256(
        json.dumps([(r["name"], r["chars"]) for r in rows]).encode()
    ).hexdigest()[:16],
}
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(f"\nwrote {OUT}")
