#!/usr/bin/env python
"""Eval harness: compare baseline vs tuned skill-router on a hand-crafted diverse set.
Runs each route.py variant with its own freshly-built index (deletes _index.json between variants),
parses injected candidate skills/MCPs, scores skill-recall / mcp-recall / noise / negative-silence.
"""

import json
import os
import re
import subprocess
import sys

BASE = r"C:\Users\Prekzursil\.claude\hooks\skill-router"
TUNED = os.path.join(BASE, "route.py")
BASELINE = os.path.join(BASE, "_fixtures", "route_v1.py")

CASES = [
    (
        "dock a phenibut analog into the GABA-B receptor and run an FEP binding free energy calculation with the schrodinger suite",
        ["phenibut-compchem"],
        ["schrodinger"],
    ),
    (
        "reverse engineer this game binary, find the function offset that holds the score and decompile it",
        ["reverse-engineering-toolkit", "binja-sigmaker"],
        ["ghidra", "ida-pro"],
    ),
    (
        "generate an AOB signature for this function in binary ninja so my trainer survives the next game update",
        ["binja-sigmaker"],
        ["binary-ninja"],
    ),
    (
        "do a thorough deep research report on GLP-1 receptor agonists for weight loss with cited sources",
        ["deep-research"],
        ["firecrawl", "exa"],
    ),
    (
        "write the tests first for this new payment feature, proper TDD with at least 80 percent coverage",
        ["tdd-workflow"],
        [],
    ),
    (
        "review this authentication code for security vulnerabilities and hardcoded secrets before I commit it",
        ["security-review", "security-bounty-hunter"],
        [],
    ),
    (
        "fan out parallel agents to refactor these ten modules at once to save time",
        ["parallel-execution-optimizer", "dmux-workflows"],
        [],
    ),
    (
        "ask codex to give a second opinion and review this implementation plan before I build it",
        ["codex-review"],
        [],
    ),
    (
        "how much have I spent on claude tokens and what is my usage breakdown this week",
        ["cost-tracking"],
        [],
    ),
    (
        "convert this horizontal landscape video into a vertical 9 by 16 clip for tiktok and reels",
        ["reframe"],
        [],
    ),
    (
        "update the codemaps and architecture docs after this big refactor",
        ["update-codemaps"],
        [],
    ),
    ("talk in caveman mode from now on to save me tokens", ["caveman"], []),
    (
        "compute the TPSA, logP and number of rotatable bonds for this SMILES string",
        [],
        ["rdkit"],
    ),
    (
        "convene a council to weigh the tradeoffs of these three architecture options",
        ["council"],
        [],
    ),
    ("thanks that works great", [], []),
    (
        "what did we decide earlier about the schrodinger license migration approach",
        [],
        ["basic-memory"],
    ),
]
MCP_FAMILIES = [
    "schrodinger",
    "rdkit",
    "tooluniverse",
    "ghidra",
    "ida-pro",
    "binary-ninja",
    "cheatengine",
    "firecrawl",
    "tavily",
    "exa",
    "basic-memory",
    "scholarly-access",
    "sonarqube",
    "codacy",
    "qlty",
]


def parse(out):
    """Extract (skills, mcps) from a route.py hook emission.

    Handles BOTH router output formats:
      * legacy/baseline: "[skill-router] candidate skills (...): /x, /y | candidate MCP tools (...): ..."
      * v3 (live):       "[skill-router] (invoke if apt...) deliberation: /z | skills: /x, /y | ... | MCP: ..."
    Skills/commands/deliberation labels are all slash-prefixed unit names; MCP families are surfaced as
    substrings of the capabilities.py labels (e.g. 'schrodinger' in 'mcp__schrodinger__*').
    """
    if not out.strip():
        return [], []
    try:
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return [], []
    if "[skill-router]" not in ctx:
        return [], []
    # Split the skill region from the MCP region on whichever MCP marker the format uses.
    skill_region, mcp_region = ctx, ""
    for marker in ("candidate MCP", "MCP:"):
        if marker in ctx:
            skill_region, mcp_region = ctx.split(marker, 1)
            break
    # Slash-prefixed names, anchored at a token boundary so embedded slashes (e.g. "go/no-go"
    # inside a deliberation label) are not captured as skills.
    skills = list(
        dict.fromkeys(re.findall(r"(?:^|[\s,])/([a-z0-9][a-z0-9-]+)", skill_region))
    )
    mcps = list(dict.fromkeys(m for m in MCP_FAMILIES if m in mcp_region))
    return skills, mcps


def run_all(route, variant):
    # Each historical/live router caches beside its own script. Preserve any existing
    # cache byte-for-byte so a comparison run never deletes or replaces live hook state.
    idx = os.path.join(os.path.dirname(route), "_index.json")
    cached = None
    cached_times = None
    try:
        if os.path.exists(idx):
            with open(idx, "rb") as fh:
                cached = fh.read()
            st = os.stat(idx)
            cached_times = (st.st_atime_ns, st.st_mtime_ns)
            os.remove(idx)
        res = []
        for i, (prompt, _, _) in enumerate(CASES):
            # Unique session_id per call so route.py's per-session dedup never suppresses an eval case
            # (identical prompts are replayed across the baseline+tuned variants).
            payload = {"prompt": prompt, "session_id": f"eval-{variant}-{i}"}
            r = subprocess.run(
                [sys.executable, route],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=60,
            )
            res.append(parse(r.stdout))
        return res
    finally:
        try:
            if cached is None:
                if os.path.exists(idx):
                    os.remove(idx)
            else:
                with open(idx, "wb") as fh:
                    fh.write(cached)
                if cached_times is not None:
                    os.utime(idx, ns=cached_times)
        except Exception:
            pass


def score(res):
    sr = mr = noise = neg_fire = 0
    pos_skill = pos_mcp = neg = 0
    for (prompt, exp_s, exp_m), (sk, mc) in zip(CASES, res):
        exp_s, exp_m = set(exp_s), set(exp_m)
        if exp_s:
            pos_skill += 1
            if exp_s & set(sk):
                sr += 1
            noise += len([s for s in sk if s not in exp_s])
        if exp_m:
            pos_mcp += 1
            if exp_m & set(mc):
                mr += 1
        if not exp_s and not exp_m:
            neg += 1
            if sk or mc:
                neg_fire += 1
    return dict(
        skill_recall=f"{sr}/{pos_skill}",
        mcp_recall=f"{mr}/{pos_mcp}",
        noise_extra_skills=noise,
        neg_false_fire=f"{neg_fire}/{neg}",
    )


base = run_all(BASELINE, "base")
tuned = run_all(TUNED, "tuned")
print("=== per-case (expected | BASELINE skills | TUNED skills) ===")
for (p, es, em), b, t in zip(CASES, base, tuned):
    tag = "+" if (set(es) & set(t[0])) or (not es) else "MISS"
    print(f"[{tag}] {p[:52]:52s} exp={es} base={b[0]} tuned={t[0]}")
print("\n=== AGGREGATE ===")
print("BASELINE:", score(base))
print("TUNED   :", score(tuned))
