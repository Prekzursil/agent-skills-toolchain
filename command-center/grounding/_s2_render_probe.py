"""LANE SKILLS2 / item 1 -- separate BUDGET-TRUNCATION from PER-FILE PARSE-FAILURE.

The two hypotheses make DIFFERENT predictions and this probe is built around that
difference, not around re-reading the files:

  H-PARSE  : a skill renders bare because ITS OWN SKILL.md cannot be parsed
             (folded scalar, >1024-char description, rejected frontmatter key).
             => the bare set is a function of FILE BYTES ONLY.
             => it is STABLE while the bytes are stable, and a byte-identical
                copy of the same skill under a different namespace is ALSO bare.

  H-BUDGET : descriptions are dropped once the cumulative listing exceeds a budget,
             lowest-priority first.
             => the bare set is a function of THE WHOLE SET + session priority.
             => it CHANGES between sessions with identical bytes, and two
                byte-identical copies can render differently.

Discriminator 1 (cross-session, free): compare THIS session's observed bare set
against the set recorded by the prior grounding lane in G-BARE-DESC.json's sibling
probe (_g5_bare_desc_probe.py hard-codes it). Any skill that FLIPPED while its
SKILL.md mtime did NOT change refutes H-PARSE for that skill.

Discriminator 2 (same-session, free): find skills that exist as BYTE-IDENTICAL (or
near-identical description) copies in two namespaces (user skills.daily vs a plugin)
where one copy renders described and the other bare. H-PARSE cannot produce that.

DETECTOR CONTROL: the script asserts (a) it parsed a non-empty description for every
name in both observed bare sets -- if any is genuinely empty on disk the premise is
wrong; and (b) it can still SEE a difference when one exists (it prints the flip set
and the non-flip set, so an all-empty output is distinguishable from "no data").
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")
JUNCTION = Path(r"C:/Users/Prekzursil/.claude/skills")
PLUGINS = Path(r"C:/Users/Prekzursil/.claude/plugins")

# ---------------------------------------------------------------- observations
# Prior grounding lane, recorded 2026-08-12 ~01:35 in _g5_bare_desc_probe.py.
PRIOR_BARE = [
    "ui-drive", "ui-invariant-walk", "vercel-deploy", "verification-loop",
    "video-convert", "video-join-concat", "video-resize-aspect", "video-stabilize",
    "voice-analyze", "voice-apply", "voice-blend", "voice-create", "volatility-3",
    "webapp-testing", "windbg-command-cookbook", "windbg-preview",
    "windows-virtualization-conflict-triage", "winui-app", "workflow-foundry",
    "workflow-monitor", "writing-plans", "wsl-vmware-cutover", "x-api", "x64dbg",
    "yeet", "zero-issue-coding",
]
PRIOR_SURVIVORS = [
    "ui-ux-pro-max", "use-image-clipboard", "using-git-worktrees",
    "using-superpowers", "verification-before-completion",
    "video-watermark-removal", "workflow-authoring", "writing-skills",
]

# THIS session (SKILLS2 grounding subagent), transcribed from my own system prompt.
NOW_BARE = PRIOR_BARE + [
    "use-image-clipboard", "using-git-worktrees",
    "verification-before-completion", "writing-skills",
]
NOW_SURVIVORS = [
    "ui-ux-pro-max", "using-superpowers", "video-watermark-removal",
    "workflow-authoring",
]

# Plugin-namespace observations from THIS session's listing (superpowers:*).
PLUGIN_BARE = [
    "executing-plans", "receiving-code-review", "requesting-code-review",
    "test-driven-development", "using-git-worktrees",
    "verification-before-completion",
]
PLUGIN_DESC = [
    "brainstorming", "dispatching-parallel-agents",
    "finishing-a-development-branch", "subagent-driven-development",
    "systematic-debugging", "using-superpowers", "writing-plans", "writing-skills",
]

SPEC_MAX_DESC = 1024  # Anthropic skill-spec description ceiling
DEFAULT_MAX_DESC_CHARS = 1536  # Claude Code skillListingMaxDescChars default


def parse_frontmatter(text: str):
    """(keys, description, folded). Handles folded/literal block scalars."""
    if not text.startswith("---"):
        return [], None, False
    end = text.find("\n---", 3)
    if end == -1:
        return [], None, False
    lines = text[3:end].splitlines()
    keys, desc, folded = [], None, False
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", lines[i])
        if m:
            key, rest = m.group(1), m.group(2)
            keys.append(key)
            if key == "description":
                rs = rest.strip()
                if rs in (">", "|", ">-", "|-", ">+", "|+"):
                    folded = True
                    buf, j = [], i + 1
                    while j < len(lines) and (
                        lines[j].startswith(("  ", "\t")) or not lines[j].strip()
                    ):
                        buf.append(lines[j].strip())
                        j += 1
                    desc = " ".join(x for x in buf if x)
                    i = j
                    continue
                desc = rs.strip("\"'")
        i += 1
    return keys, desc, folded


def scan(root: Path) -> dict:
    out = {}
    if not root.exists():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        sk = d / "SKILL.md"
        if not sk.exists():
            continue
        raw = sk.read_bytes()
        keys, desc, folded = parse_frontmatter(
            raw.decode("utf-8", errors="replace")
        )
        out[d.name] = {
            "desc": desc or "",
            "chars": len(desc or ""),
            "folded": folded,
            "keys": keys,
            "mtime": sk.stat().st_mtime,
            "sha": hashlib.sha256(raw).hexdigest()[:16],
            "desc_sha": hashlib.sha256(
                (desc or "").encode("utf-8")
            ).hexdigest()[:16],
        }
    return out


def scan_plugin_skills() -> dict:
    """name -> list of (marketplace/plugin path, record)."""
    out: dict[str, list] = {}
    if not PLUGINS.exists():
        return out
    for sk in PLUGINS.rglob("SKILL.md"):
        raw = sk.read_bytes()
        keys, desc, folded = parse_frontmatter(
            raw.decode("utf-8", errors="replace")
        )
        out.setdefault(sk.parent.name, []).append(
            {
                "path": str(sk),
                "desc": desc or "",
                "chars": len(desc or ""),
                "folded": folded,
                "mtime": sk.stat().st_mtime,
                "sha": hashlib.sha256(raw).hexdigest()[:16],
                "desc_sha": hashlib.sha256(
                    (desc or "").encode("utf-8")
                ).hexdigest()[:16],
            }
        )
    return out


daily = scan(DAILY)
plug = scan_plugin_skills()

print("=" * 78)
print("0. INVENTORY")
print(f"  skills.daily dirs with SKILL.md : {len(daily)}")
print(f"  ~/.claude/skills is junction    : {JUNCTION.is_symlink() or JUNCTION.exists()}")
print(f"  plugin skill NAMES              : {len(plug)}")
print(f"  plugin SKILL.md files           : {sum(len(v) for v in plug.values())}")

# ------------------------------------------------------- DETECTOR CONTROL (a)
print()
print("=" * 78)
print("DETECTOR CONTROL (a): every observed-bare name must have a NON-EMPTY desc")
bad = []
for n in sorted(set(PRIOR_BARE) | set(NOW_BARE)):
    r = daily.get(n)
    if r is None:
        bad.append((n, "NOT ON DISK"))
    elif r["chars"] == 0:
        bad.append((n, "EMPTY DESC ON DISK"))
print(f"  names checked : {len(set(PRIOR_BARE) | set(NOW_BARE))}")
print(f"  premise breaks: {bad if bad else 'NONE -- premise holds'}")

# ---------------------------------------------- DISCRIMINATOR 1: cross-session
print()
print("=" * 78)
print("1. DISCRIMINATOR -- cross-session flip with an mtime control")
flips = sorted(set(NOW_BARE) - set(PRIOR_BARE))
unflips = sorted(set(PRIOR_BARE) - set(NOW_BARE))
stable_surv = sorted(set(PRIOR_SURVIVORS) & set(NOW_SURVIVORS))
# G-BARE-DESC.json was written at this wall-clock; anything older than it is
# byte-stable across the two observations.
gjson = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/G-BARE-DESC.json"
)
obs_ts = gjson.stat().st_mtime if gjson.exists() else None
print(f"  prior observation recorded at : "
      f"{dt.datetime.fromtimestamp(obs_ts):%Y-%m-%d %H:%M:%S}" if obs_ts else "  ?")
print(f"  DESCRIBED -> BARE  (n={len(flips)}) : {flips}")
print(f"  BARE -> DESCRIBED  (n={len(unflips)}): {unflips}")
print(f"  survivors in BOTH  (n={len(stable_surv)}): {stable_surv}")
print()
print(f"  {'flipped skill':40s} {'chars':>6s} {'SKILL.md mtime':>20s}  changed-since-obs?")
for n in flips:
    r = daily.get(n)
    if not r:
        print(f"  {n:40s} {'--':>6s} NOT ON DISK")
        continue
    changed = obs_ts is not None and r["mtime"] > obs_ts
    print(
        f"  {n:40s} {r['chars']:6d} "
        f"{dt.datetime.fromtimestamp(r['mtime']):%Y-%m-%d %H:%M:%S}  "
        f"{'YES -- confound' if changed else 'no'}"
    )

# --------------------------------------- DISCRIMINATOR 2: two-namespace copies
print()
print("=" * 78)
print("2. DISCRIMINATOR -- same description text, two namespaces, different render")
print(f"  {'name':34s} {'user chars':>10s} {'plug chars':>10s} desc-sha match  user/plug render")
for n in sorted(set(PLUGIN_BARE) | set(PLUGIN_DESC)):
    u = daily.get(n)
    ps = plug.get(n, [])
    if not ps:
        continue
    p = ps[0]
    same = (u and u["desc_sha"] == p["desc_sha"])
    urender = "BARE" if n in NOW_BARE else ("DESC" if u else "-")
    prender = "BARE" if n in PLUGIN_BARE else "DESC"
    print(
        f"  {n:34s} {u['chars'] if u else -1:10d} {p['chars']:10d} "
        f"{'SAME' if same else 'diff':>14s}  {urender}/{prender}"
        f"{'   <== SPLIT' if urender != prender else ''}"
    )

# ------------------------------------------ H-PARSE positive-control sweep
print()
print("=" * 78)
print("3. H-PARSE direct sweep -- do the bare skills share ANY parse-shaped defect?")


def group_stats(names, label):
    vals = [daily[n] for n in names if n in daily]
    if not vals:
        print(f"  {label}: n=0")
        return
    folded = sum(1 for v in vals if v["folded"])
    over_spec = sum(1 for v in vals if v["chars"] > SPEC_MAX_DESC)
    over_cc = sum(1 for v in vals if v["chars"] > DEFAULT_MAX_DESC_CHARS)
    keyset: dict[str, int] = {}
    for v in vals:
        for k in v["keys"]:
            keyset[k] = keyset.get(k, 0) + 1
    cs = sorted(v["chars"] for v in vals)
    print(
        f"  {label:26s} n={len(vals):3d}  folded={folded:3d}  "
        f">1024={over_spec:3d}  >1536={over_cc:3d}  "
        f"chars min/med/max={cs[0]}/{cs[len(cs) // 2]}/{cs[-1]}"
    )
    print(f"      keys: {dict(sorted(keyset.items(), key=lambda kv: -kv[1]))}")


group_stats(NOW_BARE, "BARE this session")
group_stats(NOW_SURVIVORS, "SURVIVED this session")
group_stats(list(daily), "WHOLE FLEET")

folded_all = sorted(n for n, v in daily.items() if v["folded"])
print(f"\n  folded-scalar skills fleet-wide (n={len(folded_all)}): {folded_all}")
print(f"  of those, BARE this session: "
      f"{sorted(set(folded_all) & set(NOW_BARE))}")
over = sorted(
    (v["chars"], n) for n, v in daily.items() if v["chars"] > SPEC_MAX_DESC
)
print(f"\n  descriptions > {SPEC_MAX_DESC} spec max (n={len(over)}): {over}")
print(f"  of those, BARE this session: "
      f"{sorted(n for _, n in over if n in NOW_BARE)}")

# ------------------------------------------------------------ budget arithmetic
print()
print("=" * 78)
print("4. BUDGET ARITHMETIC -- what the two observations imply")
total = sum(v["chars"] for v in daily.values())
bare_now = sum(daily[n]["chars"] for n in NOW_BARE if n in daily)
bare_prior = sum(daily[n]["chars"] for n in PRIOR_BARE if n in daily)
print(f"  total description chars, {len(daily)} skills : {total}")
print(f"  chars withheld PRIOR session ({len(PRIOR_BARE)} bare) : {bare_prior}")
print(f"  chars withheld THIS  session ({len(NOW_BARE)} bare) : {bare_now}")
print(f"  delta withheld                            : {bare_now - bare_prior}")

out = {
    "daily_count": len(daily),
    "prior_bare": PRIOR_BARE,
    "now_bare": NOW_BARE,
    "flips_described_to_bare": flips,
    "flips_bare_to_described": unflips,
    "flip_mtimes": {
        n: daily[n]["mtime"] for n in flips if n in daily
    },
    "prior_observation_ts": obs_ts,
    "folded_fleet": folded_all,
    "over_spec_desc": over,
    "total_desc_chars": total,
    "withheld_prior": bare_prior,
    "withheld_now": bare_now,
}
p = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/S2-RENDER-PROBE.json"
)
p.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(f"\nwrote {p}")
