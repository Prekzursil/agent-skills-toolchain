"""LANE SKILLS2 -- (A) is the deploy hop APPEND-ONLY?  (B) negative-case census + candidates.

(A) matters for item 4. `classify_pair` compares unique-line SETS, so MODIFYING a line puts
the old text in left_only and the new text in right_only -> DIVERGED -> refused. If true,
every "improve a description" edit authored in the repo is structurally undeployable and the
item-4 plan needs a different route. Reading the source says so; that is an inference, and a
gate that reads a claim is not a gate. So call the real classifier on real fixtures.

BOTH-STATES CONTROL: the same classifier is handed (1) a purely APPENDED line, which must
come back RIGHT-AHEAD, and (2) a MODIFIED line, which must come back DIVERGED. If both return
the same verdict the probe cannot tell the two shapes apart and proves nothing.

(B) the census re-derives the brief's 69/328 negative-case number with an explicit marker
list, then ranks candidates by prefix-family size -- a skill with many same-prefix siblings
and no "do NOT use for" clause is where mis-routing actually happens.
"""

from __future__ import annotations

import importlib.util
import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(r"C:/Users/Prekzursil/source/ast-integrate")
DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")

spec = importlib.util.spec_from_file_location(
    "_drift", REPO_ROOT / "ci" / "check_skill_deploy_drift.py"
)
drift = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift)

print("=" * 78)
print("A. IS THE DEPLOY HOP APPEND-ONLY?  (real classifier, real fixtures)")
with tempfile.TemporaryDirectory() as td:
    t = Path(td)
    base = "---\nname: x\ndescription: Use when doing X.\n---\n\nbody line\n"
    (t / "deployed.md").write_text(base, encoding="utf-8")
    (t / "appended.md").write_text(base + "extra appended line\n", encoding="utf-8")
    (t / "modified.md").write_text(
        base.replace(
            "description: Use when doing X.",
            "description: Use when doing X. Do NOT use for Y, use skill-y.",
        ),
        encoding="utf-8",
    )
    v_app = drift.classify_pair(t / "deployed.md", t / "appended.md")
    v_mod = drift.classify_pair(t / "deployed.md", t / "modified.md")
    print(f"  APPEND a line   -> {v_app}")
    print(f"  MODIFY the desc -> {v_mod}")
    print(
        f"  CONTROL: verdicts differ? {v_app != v_mod}"
        f"{'' if v_app != v_mod else '   <== INERT, probe proves nothing'}"
    )
    safe_shape = v_app == drift.RIGHT_AHEAD and v_mod == drift.DIVERGED
    print(f"  VERDICT: deploy hop is APPEND-ONLY = {safe_shape}")
    print(
        "   -> a description EDIT authored in the repo can never reach skills.daily"
        if safe_shape
        else "   -> append-only claim NOT reproduced"
    )

NEG = re.compile(
    r"\b(do not use|don't use|not for|never use|rather than|instead of|"
    r"use \w[\w-]* instead|NOT a |is not a )",
    re.I,
)
SIB = re.compile(r"\buse\s+`?([a-z][a-z0-9-]{3,})`?\b", re.I)
RET = re.compile(r"\b(returns?|emits?|produces?|outputs?)\b", re.I)
WHEN = re.compile(r"\b(use when|when the user|triggers?|use this)\b", re.I)


def desc_of(p: Path) -> str:
    txt = p.read_text(encoding="utf-8", errors="replace")
    if not txt.startswith("---"):
        return ""
    end = txt.find("\n---", 3)
    lines = txt[3:end].splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"^description:(.*)$", ln)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest in (">", "|", ">-", "|-", ">+", "|+"):
            buf, j = [], i + 1
            while j < len(lines) and (
                lines[j].startswith(("  ", "\t")) or not lines[j].strip()
            ):
                buf.append(lines[j].strip())
                j += 1
            return " ".join(x for x in buf if x)
        return rest.strip("\"'")
    return ""


recs = {}
for d in sorted(p for p in DAILY.iterdir() if p.is_dir()):
    sk = d / "SKILL.md"
    if sk.exists():
        recs[d.name] = desc_of(sk)

print()
print("=" * 78)
print("B. NEGATIVE-CASE CENSUS (re-deriving the brief's 69/328)")
has_neg = [n for n, v in recs.items() if NEG.search(v)]
has_when = [n for n, v in recs.items() if WHEN.search(v)]
has_ret = [n for n, v in recs.items() if RET.search(v)]
print(f"  fleet                 {len(recs)}")
print(f"  states WHEN to use    {len(has_when)}")
print(f"  states a NEGATIVE case {len(has_neg)}   (brief said 69)")
print(f"  says what it RETURNS  {len(has_ret)}")

fam = defaultdict(list)
for n in recs:
    fam[n.split("-")[0]].append(n)
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
    "use-image-clipboard",
    "using-git-worktrees",
    "verification-before-completion",
    "writing-skills",
}
print()
print("  CANDIDATES: >=3 same-prefix siblings, NO negative case, currently RENDERED")
print(f"  {'skill':34s} {'fam':>4s} {'chars':>6s}  family")
cands = []
for n, v in sorted(recs.items()):
    f = fam[n.split("-")[0]]
    if len(f) >= 3 and not NEG.search(v) and n not in BARE and v:
        cands.append((n, len(f), len(v), sorted(x for x in f if x != n)))
for n, nf, ch, sibs in sorted(cands, key=lambda t: (-t[1], -t[2]))[:22]:
    print(f"  {n:34s} {nf:4d} {ch:6d}  {','.join(sibs[:5])}")
print(f"  total candidates: {len(cands)}")

print()
print(
    f"  TOTAL description chars in skills.daily: {sum(len(v) for v in recs.values())}"
)

Path(REPO_ROOT / "command-center/grounding/S2-NEGCASE.json").write_text(
    json.dumps(
        {
            "append_only": safe_shape,
            "verdict_append": v_app,
            "verdict_modify": v_mod,
            "fleet": len(recs),
            "has_negative": sorted(has_neg),
            "n_negative": len(has_neg),
            "n_when": len(has_when),
            "n_returns": len(has_ret),
            "total_desc_chars": sum(len(v) for v in recs.values()),
            "candidates": [
                {"name": n, "family": nf, "chars": ch, "siblings": s}
                for n, nf, ch, s in cands
            ],
        },
        indent=1,
    ),
    encoding="utf-8",
)
print("wrote S2-NEGCASE.json")
