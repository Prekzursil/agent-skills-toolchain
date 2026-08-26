#!/usr/bin/env python3
"""Identify the credential-SHAPED transcript matches my synthetic heuristic could not
clear, by showing WHERE each occurs -- never WHAT it is.

transcript_leak_check.py proved no LIVE secret (env key, codex tokens) is present, but
it left matches tagged "!! REVIEW" simply because their body is not a sequential
alphabet. Absence of the synthetic signature is not presence of a real secret, and a
40-char ghp_ string is exactly the length of a genuine GitHub PAT -- that coincidence
has to be resolved by evidence, not by shrugging at a heuristic.

So: print surrounding context with the matched value REPLACED by its own sha256[:12].
Provenance decides it. A match sitting inside a regex, a docstring, or a test fixture
is a mention; one sitting in a command output or a config value is a use.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

SESSION_DIR = Path.home() / ".claude" / "projects" / "C--Users-Prekzursil"
PATS = [
    ("OpenAI sk-", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("GitHub ghp_", re.compile(r"\bghp_[A-Za-z0-9]{20,}")),
]
WINDOW = 130


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def main() -> int:
    cands = sorted(SESSION_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime,
                   reverse=True)
    if not cands:
        print("FAILED:leak-ctx no transcript")
        return 1
    blob = cands[0].read_text(encoding="utf-8", errors="replace")

    seen: dict[str, int] = {}
    for label, rx in PATS:
        for m in rx.finditer(blob):
            v = m.group(0)
            if "abcdefghij" in v.lower():
                continue  # already positively identified as a synthetic fixture
            h = sha(v)
            seen[h] = seen.get(h, 0) + 1
            if seen[h] > 1:
                continue  # one context sample per distinct value is enough
            a = max(0, m.start() - WINDOW)
            b = min(len(blob), m.end() + WINDOW)
            ctx = blob[a:m.start()] + f"<<{h}:len{len(v)}>>" + blob[m.end():b]
            ctx = ctx.replace("\\n", " ").replace("\n", " ")
            ctx = re.sub(r"\s+", " ", ctx)
            print(f"--- {label}  sha256[:12]={h}  len={len(v)} ---")
            print(f"    ...{ctx}...")
            print()

    print("occurrence counts by value:")
    for h, n in sorted(seen.items(), key=lambda kv: -kv[1]):
        print(f"    {h}  x{n}")
    print("SUCCESS:leak-ctx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
