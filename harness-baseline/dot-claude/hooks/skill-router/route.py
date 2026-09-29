#!/usr/bin/env python
"""UserPromptSubmit hook — full-coverage skill / agent / command / MCP router (lexical UNI, v3).

THE FIX for "the agent only uses skills/MCPs when explicitly invoked." Scores each prompt against ONE
lexical index over ALL routable units — every installed skill (SKILL.md), agent and command — by
IDF-weighted token overlap, and surfaces MCP families via the shared capabilities.py table (all ~48
servers, not the old 8). Injects the top candidates so the right tool is in front of the model every turn.

Deterministic; inject-only (never blocks); fail-open; threshold-gated (silent on trivial/no-match). Index
cached 24h, rebuilt on version bump. Opt-out: SKILL_ROUTER=off, or a .disabled file.
Embeddings are intentionally DEFERRED (eval-gated): lexical first; add a semantic lane only if eval.py
shows lexical misses. Force reindex: delete _index.json.
"""

import glob
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
HOME = Path.home()
INDEX_CACHE = THIS / "_index.json"
INDEX_VER = 4
MAX_FILES = 2000

sys.path.insert(0, str(THIS))
try:
    import capabilities as _caps  # shared MCP capability map (all ~48 servers)
except Exception:
    _caps = None

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


def _tok(s):
    return {
        w for w in re.findall(r"[a-z0-9][a-z0-9+-]{2,}", s.lower()) if w not in STOP
    }


# Decision-Point Sentinel (prompt-time): route a decision-SHAPE prompt to the right deliberation skill.
# These skills have generic descriptions ("decision/plan/idea") that score below the IDF floor and are
# chronically missed, so this deterministic table surfaces them regardless of score.
_DECISION_SHAPES = [
    (
        re.compile(
            r"\b(go[ -]?no[ -]?go|should (we|i) (use|pick|choose|go with|adopt)|which (approach|option|one|way|design)|worth (it|doing|the)|trade[ -]?offs?|decide between|pros and cons|either .{1,40}\bor\b)",
            re.I,
        ),
        "/council (structured go/no-go + tradeoffs)",
    ),
    (
        re.compile(
            r"\b(stress[ -]?test|grill me|poke holes|what could go wrong|red[ -]?team|am i missing|suggest more|what else (should|could)|find (the )?flaws)\b",
            re.I,
        ),
        "/grill (adversarial stress-test + expansion; depth=program for wide scopes)",
    ),
    (
        re.compile(
            r"\b(multi[ -]?(pr|session|step|phase)|roadmap|break (this|it) (down|into)|construction plan|implementation plan for|step[ -]?by[ -]?step plan)\b",
            re.I,
        ),
        "/blueprint (multi-session construction plan)",
    ),
    (
        re.compile(
            r"\b(brainstorm|ideate|generate (ideas|options|approaches)|explore (options|directions|approaches)|what are (the|some) ways)\b",
            re.I,
        ),
        "/brainstorm (divergent ideation)",
    ),
    (
        re.compile(
            r"\b(ambiguous|unclear (what|which|how|whether)|not sure what you (mean|want)|clarify (the|my) (requirement|goal|scope))\b",
            re.I,
        ),
        "/clarify-requirements (pre-exec disambiguation)",
    ),
]


def _decision_shapes(prompt):
    out = []
    for rx, label in _DECISION_SHAPES:
        if rx.search(prompt) and label not in out:
            out.append(label)
    return out


# A YAML block-scalar header: '>' or '|' plus any chomping (+/-) and/or indentation
# (digit) indicator. `description: >` puts the real text on the FOLLOWING indented
# lines, so a same-line-only regex captures the marker itself; the unit is then
# indexed with zero descriptive tokens and cannot clear the 2-shared-token gate below.
_BLOCK_SCALAR = re.compile(r"^[|>][+\-0-9]{0,2}$")
_FM_NAME = re.compile(r"^(?:name|title):[ \t]*(.*)$")
_FM_DESC = re.compile(r"^description:[ \t]*(.*)$")


def _fm_value(text, key_rx):
    """First `key_rx` value in `text`, flattened to one line ("" if absent).

    Same-line scalars behave exactly as before. A block scalar ('>' / '|', with any
    chomping or indentation indicator) or an empty value instead consumes the
    following more-indented lines, space-joined — this index only ever tokenizes the
    description, so folding literal and folded blocks alike is lossless here.
    """
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        m = key_rx.match(ln)
        if not m:
            continue
        val = m.group(1).strip()
        if val and not _BLOCK_SCALAR.match(val):
            return val.strip("\"'")
        indent = len(ln) - len(ln.lstrip())
        block = []
        for nxt in lines[i + 1 :]:
            if not nxt.strip():
                continue
            if (len(nxt) - len(nxt.lstrip())) <= indent:
                break
            block.append(nxt.strip())
        return " ".join(block).strip()
    return ""


def _meta(md, default_name, want_first_line=False):
    head = open(md, encoding="utf-8", errors="replace").read()[:2000]
    name = _fm_value(head, _FM_NAME) or default_name.strip().strip("\"'")
    desc = _fm_value(head, _FM_DESC)
    if not desc and want_first_line:
        for line in head.splitlines():
            ln = line.strip()
            if ln and not ln.startswith(("#", "---")) and ":" not in ln[:18]:
                desc = ln[:200]
                break
    return name, desc


def _harvest(pattern, unit_type, units, df, seen, first_line=False):
    try:
        files = glob.glob(pattern, recursive=True)
    except Exception:
        return
    for md in files[:MAX_FILES]:
        try:
            default = Path(md).parent.name if unit_type == "skill" else Path(md).stem
            name, desc = _meta(md, default, want_first_line=first_line)
            key = (unit_type, name)
            if key in seen:
                continue
            seen.add(key)
            toks = _tok(name + " " + name + " " + desc)  # name counts double
            if toks:
                units.append({"name": name, "type": unit_type, "toks": sorted(toks)})
                for t in toks:
                    df[t] = df.get(t, 0) + 1
        except Exception:
            pass


def _build_index():
    units, df, seen = [], {}, set()
    _harvest(
        str(HOME / ".claude" / "skills" / "**" / "SKILL.md"), "skill", units, df, seen
    )
    _harvest(
        str(HOME / ".claude" / "plugins" / "**" / "SKILL.md"), "skill", units, df, seen
    )
    _harvest(str(HOME / ".claude" / "agents" / "*.md"), "agent", units, df, seen)
    _harvest(
        str(HOME / ".claude" / "commands" / "**" / "*.md"),
        "command",
        units,
        df,
        seen,
        first_line=True,
    )
    _harvest(
        str(Path("D:/basic-memory") / "**" / "*.md"),
        "memory",
        units,
        df,
        seen,
        first_line=True,
    )
    return {"ver": INDEX_VER, "units": units, "df": df, "n": max(1, len(units))}


def _load_index():
    try:
        if INDEX_CACHE.exists() and (time.time() - INDEX_CACHE.stat().st_mtime) < 86400:
            d = json.loads(INDEX_CACHE.read_text(encoding="utf-8"))
            if d.get("ver") == INDEX_VER:
                return d
    except Exception:
        pass
    idx = _build_index()
    try:
        INDEX_CACHE.write_text(json.dumps(idx), encoding="utf-8")
    except Exception:
        pass
    return idx


def _first_seen(sid, sig):
    """Return True the FIRST time this (session, suggestion-signature) is seen; record it.
    Per-session dedup so an identical '[skill-router]' line isn't re-injected every qualifying turn.
    Pattern borrowed from hooks/strong-tool-nudge/check.py. Fail-open: on any error, emit (don't suppress)."""
    try:
        d = Path(tempfile.gettempdir()) / "skill-router"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{sid}.seen"
        seen = set(f.read_text(encoding="utf-8").split("\n")) if f.exists() else set()
        if sig in seen:
            return False
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(sig + "\n")
        return True
    except Exception:
        return True  # fail-open: better to inject a possible repeat than crash/suppress wrongly


def main():
    try:
        if (THIS / ".disabled").exists() or os.environ.get(
            "SKILL_ROUTER", ""
        ).lower() in ("off", "0", "false"):
            return 0
        data = json.loads(sys.stdin.read() or "{}")
        prompt = str(data.get("prompt") or "")
        if len(prompt) < 30:
            return 0
        delib = _decision_shapes(prompt)
        mcps = [label for label, _hand in (_caps.match(prompt) if _caps else [])]
        ptoks = _tok(prompt)
        if len(ptoks) < 4 and not delib and not mcps:
            return 0
        idx = _load_index()
        df, n = idx.get("df", {}), idx.get("n", 1)

        def idf(t):
            return math.log(1 + n / df.get(t, 1))

        scored = []
        for e in idx.get("units", []):
            shared = ptoks & set(e["toks"])
            if len(shared) < 2:
                continue
            score = sum(idf(t) for t in shared)
            scored.append((score, e["type"], e["name"]))
        scored.sort(reverse=True)
        top = [(typ, nm) for sc, typ, nm in scored if sc >= 3.0][:6]

        buckets = {"skill": [], "agent": [], "command": [], "memory": []}
        for typ, nm in top:
            buckets.setdefault(typ, []).append(nm)

        parts = []
        if delib:
            parts.append("deliberation: " + ", ".join(delib[:2]))
        if buckets.get("skill"):
            parts.append("skills: " + ", ".join("/" + s for s in buckets["skill"][:4]))
        if buckets.get("agent"):
            parts.append("agents: " + ", ".join(buckets["agent"][:2]))
        if buckets.get("command"):
            parts.append(
                "commands: " + ", ".join("/" + c for c in buckets["command"][:2])
            )
        if buckets.get("memory"):
            parts.append(
                "memory (recall via basic-memory): " + " | ".join(buckets["memory"][:2])
            )
        if mcps:
            parts.append("MCP: " + " ; ".join(mcps[:3]))
        if not parts:
            return 0
        # Per-session dedup: suppress an identical suggestion set already injected this session, so the
        # router doesn't emit the same '[skill-router]' line every qualifying turn. Signature = the sorted
        # set of suggested units (skills + agents + commands + memory + deliberation labels + MCP families).
        sig_items = sorted(
            delib
            + buckets.get("skill", [])
            + buckets.get("agent", [])
            + buckets.get("command", [])
            + buckets.get("memory", [])
            + mcps
        )
        sid = (
            str(data.get("session_id") or "default")
            .replace("/", "_")
            .replace("\\", "_")
        )
        sig = hashlib.md5(
            "".join(sig_items).encode("utf-8", "replace"), usedforsecurity=False
        ).hexdigest()[:12]
        if not _first_seen(sid, sig):
            return 0
        msg = "[skill-router] (invoke if apt, else ignore) " + " | ".join(parts)
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
