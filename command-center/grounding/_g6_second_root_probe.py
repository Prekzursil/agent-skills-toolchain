"""Do the 8 SURVIVORS have a SECOND SKILL.md copy on the estate that the 26 BARE lack?

Hypothesis under test (H-C): the listing renders descriptions from an enumeration
that exhausts a budget alphabetically, and the 8 late survivors are rendered by a
SECOND, separately-budgeted enumeration pass over another skills root.

DETECTOR CONTROL: 'using-git-worktrees' is a KNOWN plugin skill and MUST show >=2
copies. If it shows 1, the walker is broken and every zero below is meaningless.
"""

from __future__ import annotations

import collections
from pathlib import Path

BARE = [
    "ui-drive", "ui-invariant-walk", "vercel-deploy", "verification-loop",
    "video-convert", "video-join-concat", "video-resize-aspect", "video-stabilize",
    "voice-analyze", "voice-apply", "voice-blend", "voice-create", "volatility-3",
    "webapp-testing", "windbg-command-cookbook", "windbg-preview",
    "windows-virtualization-conflict-triage", "winui-app", "workflow-foundry",
    "workflow-monitor", "writing-plans", "wsl-vmware-cutover", "x-api", "x64dbg",
    "yeet", "zero-issue-coding",
]
SURVIVORS = [
    "ui-ux-pro-max", "use-image-clipboard", "using-git-worktrees", "using-superpowers",
    "verification-before-completion", "video-watermark-removal", "workflow-authoring",
    "writing-skills",
]
TARGETS = set(BARE) | set(SURVIVORS)

ROOTS = [
    Path(r"C:/Users/Prekzursil/.claude/skills.daily"),
    Path(r"C:/Users/Prekzursil/.claude/plugins"),
    Path(r"C:/Users/Prekzursil/.claude/_main-monitor-skills"),
    Path(r"C:/Users/Prekzursil/.agents/skills"),
]

hits = collections.defaultdict(list)
for root in ROOTS:
    if not root.exists():
        print(f"  (root absent: {root})")
        continue
    for sk in root.rglob("SKILL.md"):
        nm = sk.parent.name
        if nm in TARGETS:
            hits[nm].append(str(sk))

ctrl = len(hits.get("using-git-worktrees", []))
print(f"DETECTOR CONTROL: using-git-worktrees copies = {ctrl} (must be >= 2)")
if ctrl < 2:
    print("  -> WALKER BROKEN; all counts below are void")
print()

print(f"{'name':42s} {'copies':>6s}  class  roots")
for n in sorted(TARGETS):
    cls = "BARE" if n in BARE else "SURV"
    paths = hits.get(n, [])
    tags = []
    for p in paths:
        if "plugins" in p:
            tags.append("plugin")
        elif "skills.daily" in p:
            tags.append("daily")
        elif ".agents" in p:
            tags.append("vault")
        elif "_main-monitor" in p:
            tags.append("monitor")
    print(f"{n:42s} {len(paths):6d}  {cls:5s}  {','.join(sorted(set(tags)))}")

print()
for label, group in (("BARE", BARE), ("SURVIVORS", SURVIVORS)):
    counts = collections.Counter(len(hits.get(n, [])) for n in group)
    print(f"{label}: copy-count distribution = {dict(sorted(counts.items()))}")
