"""Measure rule frontmatter, token cost, and repo-vs-live drift.

Read-only. Emits JSON to stdout.
Windows/CRLF-safe: every read uses newline="" then LF-normalises for comparison.
"""

import glob
import hashlib
import json
import os
import re
import sys

REPO = r"C:/Users/Prekzursil/source/ast-integrate"
LIVE_ROOTS = [
    r"C:/Users/Prekzursil/.claude/rules",
    r"C:/Users/Prekzursil/.agents/rules",
]


def read_raw(path):
    with open(path, "rb") as fh:
        return fh.read()


def lf(b):
    return b.replace(b"\r\n", b"\n")


def parse_frontmatter(text):
    """Return (has_fm, fm_dict_raw_lines, body_offset)."""
    if not text.startswith("---"):
        return False, {}, 0
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return False, {}, 0
    block = m.group(1)
    d = {}
    key = None
    for line in block.split("\n"):
        line = line.rstrip("\r")
        if re.match(r"^\s*-\s", line) and key:
            d.setdefault(key + "__list", []).append(line.strip()[1:].strip())
            continue
        mm = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if mm:
            key = mm.group(1)
            d[key] = mm.group(2).strip()
    return True, d, m.end()


def tok_est(text):
    """Two independent estimators; report both (never a single signal)."""
    chars = len(text)
    words = len(text.split())
    return {
        "chars": chars,
        "words": words,
        "tok_char_div4": round(chars / 4),
        "tok_word_x1_33": round(words * 1.33),
    }


def scan(root, pattern="**/*.md"):
    out = {}
    for p in sorted(glob.glob(os.path.join(root, pattern), recursive=True)):
        rel = os.path.relpath(p, root).replace("\\", "/")
        raw = read_raw(p)
        text = lf(raw).decode("utf-8", errors="replace")
        has_fm, fm, off = parse_frontmatter(text)
        out[rel] = {
            "path": p.replace("\\", "/"),
            "has_frontmatter": has_fm,
            "frontmatter": fm,
            "has_paths_key": "paths" in fm,
            "paths_value": fm.get("paths", fm.get("paths__list")),
            "sha256_lf": hashlib.sha256(lf(raw)).hexdigest(),
            "bytes_raw": len(raw),
            "crlf_count": raw.count(b"\r\n"),
            **tok_est(text),
        }
    return out


def main():
    result = {"repo": {}, "live": {}, "tokenizer": None}

    result["repo"] = scan(os.path.join(REPO, "rules"))

    for lr in LIVE_ROOTS:
        if os.path.isdir(lr):
            result["live"][lr] = scan(lr)
        else:
            result["live"][lr] = {"__MISSING__": True}

    # AGENTS.md / CLAUDE.md at repo root and live
    extras = {}
    for label, p in [
        ("repo:AGENTS.md", os.path.join(REPO, "AGENTS.md")),
        ("repo:CLAUDE.md", os.path.join(REPO, "CLAUDE.md")),
        ("live:~/.claude/AGENTS.md", r"C:/Users/Prekzursil/.claude/AGENTS.md"),
        ("live:~/.claude/CLAUDE.md", r"C:/Users/Prekzursil/.claude/CLAUDE.md"),
        ("live:~/CLAUDE.md", r"C:/Users/Prekzursil/CLAUDE.md"),
        ("live:~/AGENTS.md", r"C:/Users/Prekzursil/AGENTS.md"),
    ]:
        if os.path.isfile(p):
            raw = read_raw(p)
            text = lf(raw).decode("utf-8", errors="replace")
            has_fm, fm, off = parse_frontmatter(text)
            extras[label] = {
                "has_frontmatter": has_fm,
                "frontmatter": fm,
                "sha256_lf": hashlib.sha256(lf(raw)).hexdigest(),
                "bytes_raw": len(raw),
                **tok_est(text),
            }
        else:
            extras[label] = {"__MISSING__": True}
    result["extras"] = extras

    # try a real tokenizer for a second, mechanically different token signal
    try:
        import tiktoken  # noqa

        enc = tiktoken.get_encoding("cl100k_base")
        result["tokenizer"] = "tiktoken/cl100k_base"

        def real(path):
            raw = read_raw(path)
            return len(enc.encode(lf(raw).decode("utf-8", errors="replace")))

        for rel, d in result["repo"].items():
            d["tok_tiktoken"] = real(d["path"])
        for lr, files in result["live"].items():
            if "__MISSING__" in files:
                continue
            for rel, d in files.items():
                d["tok_tiktoken"] = real(d["path"])
    except Exception as e:  # noqa
        result["tokenizer"] = "UNAVAILABLE: %s" % e

    json.dump(result, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
