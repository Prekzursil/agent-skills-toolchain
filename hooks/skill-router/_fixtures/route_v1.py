#!/usr/bin/env python
"""UserPromptSubmit hook — skill / MCP router.

THE FIX for "the agent only uses skills/MCPs when explicitly invoked": skills are invoked only when the
model notices a match against ~248 one-line descriptions, and MCP tools are deferred behind ToolSearch.
This hook scores each prompt against a cached local skill index (name+description from every SKILL.md) plus
a curated MCP-server keyword map, and INJECTS the top candidates so the right skill/MCP is in front of the
model every turn — without the model having to remember it.

Deterministic IDF-weighted keyword scoring; inject-only (never blocks); fail-open; threshold-gated so it
stays silent on trivial/no-match prompts. Index is cached 24h. Opt-out: SKILL_ROUTER=off, or .disabled file.
"""

import glob
import json
import math
import os
import re
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
HOME = Path.home()
INDEX_CACHE = THIS / "_index.json"
MAX_FILES = 700

STOP = set(
    (
        "the a an and or to of in on for with is are be this that it as at by from your you i we us our "
        "use using used when whether not no into over under via per any all only just like such than then "
        "skill skills user agent claude code task tasks run runs running do does doing help need needs want "
        "wants make makes get gets set sets new add adds also more most less few many other another each "
        "before after during while if else can could should would may might will shall must its their them "
        "what which who how why where here there about across against between within without around through"
    ).split()
)

MCP_HINTS = [
    (
        r"\b(dock|docking|glide|fep|schrod|binding|prepwiz|ligprep|admet|pymol|mmgbsa|pka)\b",
        "mcp__schrodinger__* (docking / FEP / ADMET / structure prep)",
    ),
    (
        r"\b(smiles|molecul|descriptor|tanimoto|cheminform|rdkit|scaffold|fingerprint|tpsa)\b",
        "mcp__rdkit__* (cheminformatics / descriptors)",
    ),
    (
        r"\b(pharmacolog|affinity|target|drug|clinical|disease|gene|protein|tooluniverse|ki\b)",
        "mcp__tooluniverse__* (2500+ pharmacology / bio tools)",
    ),
    (
        r"\b(paper|papers|citation|pubmed|scholar|doi|preprint|literature|arxiv)\b",
        "mcp__scholarly-access__* / firecrawl research tools",
    ),
    (
        r"\b(reverse|disassembl|ghidra|\bida\b|decompil|binary|offset|x64dbg|cheat ?engine|frida)\b",
        "mcp__ghidra-mcp__ / ida-pro-mcp / binary-ninja-mcp / cheatengine",
    ),
    (
        r"\b(memory|recall|remember|prior work|earlier session|decision log)\b",
        "mcp__basic-memory__* (semantic memory vault)",
    ),
    (
        r"\b(scrape|crawl|web search|search online|fetch url|firecrawl|tavily)\b",
        "mcp__firecrawl__ / tavily / exa (web data)",
    ),
    (
        r"\b(sonar|coverage|codacy|deepsource|qlty|lint quality|quality gate)\b",
        "mcp__sonarqube__ / codacy / qlty (code quality)",
    ),
]


def _tok(s):
    return {
        w for w in re.findall(r"[a-z0-9][a-z0-9+-]{2,}", s.lower()) if w not in STOP
    }


def _build_index():
    skills, df = [], {}
    seen = set()
    bases = [HOME / ".claude" / "skills", HOME / ".claude" / "plugins"]
    files = []
    for b in bases:
        try:
            files += glob.glob(str(b / "**" / "SKILL.md"), recursive=True)
        except Exception:
            pass
        if len(files) > MAX_FILES:
            break
    for md in files[:MAX_FILES]:
        try:
            head = open(md, encoding="utf-8", errors="replace").read()[:2000]
            nm = re.search(r"(?m)^name:\s*(.+)$", head)
            ds = re.search(r"(?m)^description:\s*(.+)$", head)
            name = (nm.group(1) if nm else Path(md).parent.name).strip().strip("\"'")
            if name in seen:
                continue
            seen.add(name)
            desc = (ds.group(1) if ds else "").strip().strip("\"'")
            toks = _tok(name + " " + name + " " + desc)  # name counts double
            if toks:
                skills.append({"name": name, "toks": sorted(toks)})
                for t in toks:
                    df[t] = df.get(t, 0) + 1
        except Exception:
            pass
    return {"skills": skills, "df": df, "n": max(1, len(skills))}


def _load_index():
    try:
        if INDEX_CACHE.exists() and (time.time() - INDEX_CACHE.stat().st_mtime) < 86400:
            return json.loads(INDEX_CACHE.read_text(encoding="utf-8"))
    except Exception:
        pass
    idx = _build_index()
    try:
        INDEX_CACHE.write_text(json.dumps(idx), encoding="utf-8")
    except Exception:
        pass
    return idx


def main():
    try:
        if (THIS / ".disabled").exists() or os.environ.get(
            "SKILL_ROUTER", ""
        ).lower() in ("off", "0", "false"):
            return 0
        data = json.loads(sys.stdin.read() or "{}")
        prompt = str(data.get("prompt") or "")
        if len(prompt) < 30:
            return 0  # trivial / conversational
        ptoks = _tok(prompt)
        if len(ptoks) < 4:
            return 0
        idx = _load_index()
        df, n = idx.get("df", {}), idx.get("n", 1)
        scored = []
        for e in idx.get("skills", []):
            shared = ptoks & set(e["toks"])
            if len(shared) < 2:
                continue
            score = sum(math.log(1 + n / df.get(t, 1)) for t in shared)
            scored.append((score, len(shared), e["name"]))
        scored.sort(reverse=True)
        top = [nm for sc, sh, nm in scored if sc >= 3.0][:4]
        mcps = []
        low = prompt.lower()
        for pat, hint in MCP_HINTS:
            if re.search(pat, low) and hint not in mcps:
                mcps.append(hint)
        if not top and not mcps:
            return 0
        parts = []
        if top:
            parts.append(
                "candidate skills (invoke via the Skill tool if apt, else ignore): "
                + ", ".join("/" + t for t in top)
            )
        if mcps:
            parts.append(
                "candidate MCP tools (load via ToolSearch if needed): "
                + " ; ".join(mcps[:3])
            )
        msg = "[skill-router] " + " | ".join(parts)
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": msg,
                    }
                }
            )
        )
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
