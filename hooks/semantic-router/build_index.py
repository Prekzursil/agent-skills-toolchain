#!/usr/bin/env python
"""Semantic-router index builder.

Embeds the BODY of every skill (the decisive routing signal — not just the
frontmatter blurb) plus every MCP server (name + tool-name keywords + curated
purpose), and — so this index can fully supersede the lexical router's coverage —
every agent and command too. Stores a lightweight local index:

    index/index.npz   vecs (N x 768 float32, L2-normalized) + names/kinds/invokes/shas
    index/manifest.json   model, dim, counts, built_at, source paths

Incremental: a unit is re-embedded only when its content hash (sha of the exact
embedded text) changes, so day-to-day rebuilds touch a handful of edited bodies,
not all ~360 units. Run:  python build_index.py [--rebuild] [--quiet]

Fail-soft: a unit whose embedding call fails is skipped (kept out of the index)
and reported; the next run retries it. Never deletes a good index on a bad run.
"""

import array
import glob
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
HOME = Path.home()
INDEX_DIR = THIS / "index"
VECS_F32 = (
    INDEX_DIR / "vecs.f32"
)  # raw little-endian float32, count*dim, L2-normalized, row-major
META_JSON = (
    INDEX_DIR / "meta.json"
)  # {model,dim,count,by_kind,...,rows:[{name,kind,invoke,sha,excerpt}]}

SKILLS_GLOB = str(HOME / ".agents" / "skills" / "*" / "SKILL.md")
AGENTS_GLOB = str(HOME / ".claude" / "agents" / "*.md")
COMMANDS_GLOB = str(HOME / ".claude" / "commands" / "**" / "*.md")
MCP_JSON = next(
    (p for p in (HOME / ".mcp.json", HOME / ".claude.json") if p.exists()),
    HOME / ".mcp.json",
)  # fleet moved ~/.mcp.json -> ~/.claude.json (root mcpServers) 2026-09;
# keep the old path first so a restored canonical file wins again.

BODY_CAP = 1200  # chars of skill body (empirically best: a 1200-char body + 2x-weighted
# description beat a 5000-char body on mean expected-rank 13.4 vs 25.6 and
# cut noise standout — the long body dilutes the routing trigger)
SHORT_CAP = 1200  # chars for agents / commands (they are prompts)

sys.path.insert(0, str(THIS))
import embed as _embed  # noqa: E402

# capabilities.py lives in the sibling lexical router; reuse its curated labels to
# enrich MCP server text. Fail-open: missing/broken -> MCP uses name + mcp_hints only.
try:
    sys.path.insert(0, str(HOME / ".claude" / "hooks" / "skill-router"))
    import capabilities as _caps  # type: ignore

    _CAP_LABELS = [lab for _rx, lab, _h in _caps._RAW]
except Exception:
    _CAP_LABELS = []

try:
    import mcp_hints as _hints

    MCP_HINTS = _hints.MCP_HINTS
except Exception:
    MCP_HINTS = {}


def _read(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# A YAML block-scalar header: '>' or '|' plus any chomping (+/-) and/or indentation
# (digit) indicator. `description: >` puts the real text on the FOLLOWING indented
# lines, so a same-line-only regex captures the marker itself and the whole blurb is
# lost (6 of 345 canonical SKILL.md files use this form).
_BLOCK_SCALAR = re.compile(r"^[|>][+\-0-9]{0,2}$")
_FM_NAME = re.compile(r"(?i)^(?:name|title):[ \t]*(.*)$")
_FM_DESC = re.compile(r"(?i)^description:[ \t]*(.*)$")


def _fm_value(fm, key_rx):
    """First frontmatter value matching `key_rx`, flattened to a single line.

    Same-line scalars behave exactly as before. A block scalar ('>' / '|', with any
    chomping or indentation indicator) or an empty value instead consumes the
    following more-indented lines. Both folded and literal blocks are space-joined:
    every consumer here treats the description as a one-line routing blurb (embedded
    doc head, 'use when' weighting, 200-char excerpt, token bag).
    """
    lines = fm.split("\n")
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


def _split_frontmatter(text):
    """Return (name, description, body). Tolerant of files with or without frontmatter."""
    name = desc = ""
    body = text
    if text.startswith("---"):
        m = re.search(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
        if m:
            fm, body = m.group(1), text[m.end() :]
            name = _fm_value(fm, _FM_NAME)
            desc = _fm_value(fm, _FM_DESC)
    return name, desc, body


def _sha(s):
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()[:16]


def _headings(body):
    """Space-joined section headings — a compact, discriminative topic signature."""
    hs = re.findall(r"(?m)^#{1,4}\s+(.+?)\s*$", body)
    return " ".join(h.strip("# ").strip() for h in hs[:25])


def _doc_text(kind, name, desc, body, body_cap):
    """Trigger-weighted document text. Empirically, mean-pooled embeddings of the RAW
    5k-char body dilute discrimination (a distractor can outscore the right skill); leading
    with name + the 'use when' description + section headings, THEN a trimmed body, restores
    separation while still embedding the body (the decisive recall signal)."""
    head = f"{kind}: {name}. {desc}".strip()
    when = f"use when: {desc}" if desc else ""
    topics = _headings(body)
    topics = f"topics: {topics}" if topics else ""
    parts = [p for p in (head, when, topics, body.strip()[:body_cap]) if p]
    return "\n".join(parts)


def _excerpt(desc, body):
    e = (desc or "").strip()
    if not e:
        for ln in body.splitlines():
            ln = ln.strip()
            if ln and not ln.startswith(("#", "---", "```")):
                e = ln
                break
    return e[:200]


def _skill_units():
    out = []
    for md in glob.glob(SKILLS_GLOB):
        txt = _read(md)
        if not txt:
            continue
        default = Path(md).parent.name
        name, desc, body = _split_frontmatter(txt)
        name = name or default
        text = _doc_text("skill", name, desc, body, BODY_CAP)
        out.append(
            {
                "name": name,
                "kind": "skill",
                "invoke": "/" + name,
                "text": text,
                "excerpt": _excerpt(desc, body),
            }
        )
    return out


def _agent_units():
    out = []
    for md in glob.glob(AGENTS_GLOB):
        txt = _read(md)
        if not txt:
            continue
        name, desc, body = _split_frontmatter(txt)
        name = name or Path(md).stem
        text = _doc_text("agent", name, desc, body, SHORT_CAP)
        out.append(
            {
                "name": name,
                "kind": "agent",
                "invoke": name,
                "text": text,
                "excerpt": _excerpt(desc, body),
            }
        )
    return out


def _command_units():
    out, seen = [], set()
    for md in glob.glob(COMMANDS_GLOB, recursive=True):
        txt = _read(md)
        if not txt:
            continue
        name, desc, body = _split_frontmatter(txt)
        name = Path(md).stem
        if name in seen:
            continue
        seen.add(name)
        text = _doc_text("command", name, desc, body, SHORT_CAP)
        out.append(
            {
                "name": name,
                "kind": "command",
                "invoke": "/" + name,
                "text": text,
                "excerpt": _excerpt(desc, body),
            }
        )
    return out


def _mcp_units():
    out = []
    try:
        servers = list(
            json.loads(MCP_JSON.read_text(encoding="utf-8"))
            .get("mcpServers", {})
            .keys()
        )
    except Exception:
        servers = []
    for s in servers:
        parts = [f"MCP server {s.replace('-', ' ').replace('_', ' ')}."]
        hint = MCP_HINTS.get(s)
        if hint:
            parts.append(hint)
        for lab in _CAP_LABELS:
            if (f"mcp__{s}__" in lab) or (s in lab):
                clean = re.sub(r"mcp__[a-z0-9_-]+__\*?", "", lab).strip(" —-/")
                if clean and clean not in parts:
                    parts.append(clean)
        text = " ".join(dict.fromkeys(parts))
        out.append(
            {
                "name": s,
                "kind": "mcp",
                "invoke": f"mcp__{s}__*",
                "text": text,
                "excerpt": (hint or text)[:200],
            }
        )
    return out


def _load_old():
    """(kind,name) -> (sha, vector_list) from the existing index, for incremental reuse."""
    cache = {}
    try:
        meta = json.loads(META_JSON.read_text(encoding="utf-8"))
        dim, rows = int(meta["dim"]), meta["rows"]
        raw = array.array("f")
        with open(VECS_F32, "rb") as f:
            raw.frombytes(f.read())
        for i, r in enumerate(rows):
            vec = raw[i * dim : (i + 1) * dim].tolist()
            if len(vec) == dim:
                cache[(r["kind"], r["name"])] = (r["sha"], vec)
    except Exception:
        pass
    return cache


def main(argv):
    rebuild = "--rebuild" in argv
    quiet = "--quiet" in argv
    t0 = time.time()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    ok, detail = _embed.health()
    if not ok:
        print(f"FAILED:build-index ollama-health {detail}")
        return 1

    units = _skill_units() + _mcp_units() + _agent_units() + _command_units()
    if not units:
        print("FAILED:build-index no-units-harvested")
        return 1

    old = {} if rebuild else _load_old()
    # Bake the retrieval DOC_PREFIX into both the embedded text AND the change-hash, so a
    # prefix-scheme change invalidates the cache and forces a clean re-embed.
    for u in units:
        u["embed_text"] = _embed.DOC_PREFIX + u["text"]
        u["sha"] = _sha(u["embed_text"])

    reuse_rows, to_embed = {}, []
    for u in units:
        hit = old.get((u["kind"], u["name"]))
        if hit and hit[0] == u["sha"] and len(hit[1]) == _embed.DIM:
            reuse_rows[(u["kind"], u["name"])] = hit[1]
        else:
            to_embed.append(u)

    def prog(done, total):
        if not quiet:
            sys.stderr.write(f"\r  embedding {done}/{total}")
            sys.stderr.flush()

    new_vecs = {}
    failed = []
    if to_embed:
        vecs = _embed.embed_many([u["embed_text"] for u in to_embed], progress=prog)
        if not quiet:
            sys.stderr.write("\n")
        for u, v in zip(to_embed, vecs):
            if v is None or len(v) != _embed.DIM:
                failed.append(f"{u['kind']}:{u['name']}")
            else:
                new_vecs[(u["kind"], u["name"])] = list(v)

    flat = array.array("f")
    meta_rows = []
    for u in units:
        key = (u["kind"], u["name"])
        vec = new_vecs.get(key) or reuse_rows.get(key)
        if vec is None or len(vec) != _embed.DIM:
            continue  # failed this run; retried next time
        flat.extend(vec)
        meta_rows.append(
            {
                "name": u["name"],
                "kind": u["kind"],
                "invoke": u["invoke"],
                "sha": u["sha"],
                "excerpt": u["excerpt"],
            }
        )

    if not meta_rows:
        print("FAILED:build-index all-embeds-failed (ollama?)")
        return 1

    by_kind = {}
    for r in meta_rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(VECS_F32) + f".tmp{os.getpid()}"
    with open(tmp, "wb") as f:
        f.write(flat.tobytes())
    os.replace(tmp, VECS_F32)
    meta = {
        "model": _embed.MODEL,
        "dim": _embed.DIM,
        "count": len(meta_rows),
        "by_kind": by_kind,
        "reused": len(reuse_rows),
        "embedded": len(new_vecs),
        "failed": failed,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 1),
        "sources": {
            "skills": SKILLS_GLOB,
            "agents": AGENTS_GLOB,
            "commands": COMMANDS_GLOB,
            "mcp": str(MCP_JSON),
        },
        "rows": meta_rows,
    }
    META_JSON.write_text(json.dumps(meta), encoding="utf-8")

    print(
        f"SUCCESS:build-index count={len(meta_rows)} by_kind={by_kind} "
        f"reused={len(reuse_rows)} embedded={len(new_vecs)} "
        f"failed={len(failed)} elapsed={meta['elapsed_s']}s"
    )
    if failed and not quiet:
        print("  failed (will retry next run): " + ", ".join(failed[:20]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
