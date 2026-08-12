"""Why do 26 curated skills render with NO description in the live skill listing?

Deterministic probe. Emits, per skill, in ALPHABETICAL order (the render order):
  name, description char count, cumulative chars, folded?, frontmatter key set,
  SKILL.md mtime, and whether the name also exists under ~/.claude/plugins.

The 26 BARE names are hard-coded from the ACTUAL listing in this session's system
prompt (an independent observation from the earlier lens). The 8 SURVIVORS are the
skills alphabetically AFTER the first bare entry that still render a description.

DETECTOR CONTROL: the script asserts it parsed a description for every one of the
26 bare names. If it cannot, the on-disk premise is wrong and the whole probe is void.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")
PLUGINS = Path(r"C:/Users/Prekzursil/.claude/plugins")

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


def parse_frontmatter(text: str):
    """Return (keys, description, folded_flag). Handles folded/literal block scalars."""
    if not text.startswith("---"):
        return [], None, False
    end = text.find("\n---", 3)
    if end == -1:
        return [], None, False
    block = text[3:end]
    lines = block.splitlines()
    keys, desc, folded = [], None, False
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", ln)
        if m:
            key, rest = m.group(1), m.group(2)
            keys.append(key)
            if key == "description":
                rest_s = rest.strip()
                if rest_s in (">", "|", ">-", "|-", ">+", "|+"):
                    folded = True
                    buf = []
                    j = i + 1
                    while j < len(lines) and (lines[j].startswith(("  ", "\t")) or not lines[j].strip()):
                        buf.append(lines[j].strip())
                        j += 1
                    desc = " ".join(x for x in buf if x)
                    i = j
                    continue
                desc = rest_s.strip("\"'")
        i += 1
    return keys, desc, folded


plugin_names = set()
if PLUGINS.exists():
    for p in PLUGINS.rglob("SKILL.md"):
        plugin_names.add(p.parent.name)

rows = []
for d in sorted([p for p in DAILY.iterdir() if p.is_dir()], key=lambda p: p.name):
    sk = d / "SKILL.md"
    if not sk.exists():
        rows.append({"name": d.name, "desc_chars": None, "note": "NO SKILL.md"})
        continue
    text = sk.read_text(encoding="utf-8", errors="replace")
    keys, desc, folded = parse_frontmatter(text)
    rows.append({
        "name": d.name,
        "desc_chars": len(desc) if desc else 0,
        "folded": folded,
        "keys": keys,
        "mtime": sk.stat().st_mtime,
        "size": sk.stat().st_size,
        "in_plugins": d.name in plugin_names,
    })

# DETECTOR CONTROL --------------------------------------------------------
by_name = {r["name"]: r for r in rows}
missing = [n for n in BARE if n not in by_name]
zero_desc = [n for n in BARE if by_name.get(n, {}).get("desc_chars", 0) == 0]
print("DETECTOR CONTROL")
print(f"  total skill dirs parsed : {len(rows)}")
print(f"  BARE names not on disk  : {missing}")
print(f"  BARE names w/ 0-char desc on disk: {zero_desc}")
if missing or zero_desc:
    print("  -> PREMISE BROKEN, probe void")
print()

cum = 0
first_bare_cum = None
print(f"{'name':42s} {'chars':>6s} {'cum':>8s} fold plug  class")
for r in rows:
    n = r["name"]
    dc = r.get("desc_chars") or 0
    cum += dc
    cls = "BARE" if n in BARE else ("SURV" if n in SURVIVORS else "")
    if n == BARE[0]:
        first_bare_cum = cum - dc
    if cls or (first_bare_cum is not None and not cls):
        print(f"{n:42s} {dc:6d} {cum:8d} "
              f"{'Y' if r.get('folded') else '.':>4s} "
              f"{'Y' if r.get('in_plugins') else '.':>4s}  {cls}")

print()
print(f"CUMULATIVE CHARS BEFORE FIRST BARE ENTRY ({BARE[0]}): {first_bare_cum}")
print(f"TOTAL DESCRIPTION CHARS (all {len(rows)}): {cum}")

# Distinguishers between BARE and SURVIVORS
def stat(group, label):
    vals = [by_name[n] for n in group if n in by_name]
    print(f"\n{label}: n={len(vals)}")
    print(f"  folded      : {sum(1 for v in vals if v.get('folded'))}")
    print(f"  in_plugins  : {sum(1 for v in vals if v.get('in_plugins'))}")
    dcs = sorted(v['desc_chars'] for v in vals)
    print(f"  desc_chars  : min={dcs[0]} med={dcs[len(dcs)//2]} max={dcs[-1]}")
    keyset = {}
    for v in vals:
        for k in v.get("keys", []):
            keyset[k] = keyset.get(k, 0) + 1
    print(f"  keys        : {dict(sorted(keyset.items(), key=lambda kv: -kv[1]))}")
    mt = sorted(v["mtime"] for v in vals)
    import datetime
    print(f"  mtime range : {datetime.datetime.fromtimestamp(mt[0]):%Y-%m-%d} .. "
          f"{datetime.datetime.fromtimestamp(mt[-1]):%Y-%m-%d}")

stat(BARE, "BARE (26)")
stat(SURVIVORS, "SURVIVORS (8)")

out = Path(r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/G-BARE-DESC.json")
out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
print(f"\nwrote {out}")
