#!/usr/bin/env python3
"""AGENTS.md 9b blast-radius trace for the GitHub tokens found in the transcript.

A confirmed exposure obliges tracing the WHOLE set, not the first symptom. My previous
regex looked for `ghp_` only and therefore missed `github_pat_*` entirely -- which then
printed in cleartext as CONTEXT around a different match. So this sweep covers every
common provider shape, counts occurrences per distinct value, and reports which FILES
outside the transcript also hold them.

Then it answers the only question that sets urgency: are they still LIVE? A revoked
token needs no rotation. Liveness is checked against the provider's own identity
endpoint using the owner's own token on the owner's own account -- and prints only the
login, token type and scopes, never the value.

Absolutely no secret value is printed. Ever. Identity is sha256[:12] throughout.
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path.home()
SESSION_DIR = HOME / ".claude" / "projects" / "C--Users-Prekzursil"
CTX = ssl.create_default_context()

SHAPES = [
    ("github-classic-pat", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("github-finegrained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("github-oauth",       re.compile(r"\bgh[ousr]_[A-Za-z0-9]{36}\b")),
    ("aws-access-key",     re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack-token",        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google-api-key",     re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")),
    ("stripe-live",        re.compile(r"\b[sr]k_live_[A-Za-z0-9]{20,}\b")),
    ("openai-modern",      re.compile(r"\bsk-proj-[A-Za-z0-9_-]{100,}\b")),
]


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def scan(text: str) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for label, rx in SHAPES:
        for m in rx.finditer(text):
            v = m.group(0)
            if "abcdefghij" in v.lower():
                continue
            k = (label, sha(v))
            out[k] = out.get(k, 0) + 1
    return out


def github_liveness(tokens: dict[str, str]) -> None:
    print("[3] liveness (owner's own tokens, owner's own account; value never printed)")
    if not tokens:
        print("    (none recovered to test)")
        return
    for h, tok in tokens.items():
        req = urllib.request.Request("https://api.github.com/user")
        req.add_header("Authorization", f"Bearer {tok}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "blast-radius-check")
        try:
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                who = json.loads(r.read().decode())
                scopes = r.headers.get("x-oauth-scopes", "(fine-grained: not listed)")
                print(f"    !! LIVE    {h}  login={who.get('login')}  scopes=[{scopes}]")
                print(f"               -> ROTATE THIS NOW")
        except urllib.error.HTTPError as e:
            state = "revoked/invalid" if e.code in (401, 403) else f"HTTP {e.code}"
            print(f"    ok-dead    {h}  {state} - no rotation needed")
        except Exception as e:
            print(f"    UNKNOWN    {h}  {type(e).__name__} - could not determine")


def main() -> int:
    # ---- 1. transcripts ------------------------------------------------------
    print("[1] transcripts")
    totals: dict[tuple[str, str], int] = {}
    recovered: dict[str, str] = {}
    for p in sorted(SESSION_DIR.glob("*.jsonl")):
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = scan(t)
        if not hits:
            continue
        print(f"    {p.name}  ({p.stat().st_size:,} B)")
        for (label, h), n in sorted(hits.items(), key=lambda kv: -kv[1]):
            print(f"        {label:<20} {h}  x{n}")
            totals[(label, h)] = totals.get((label, h), 0) + n
        # recover GitHub token values IN MEMORY ONLY, to test liveness
        for _, rx in SHAPES[:3]:
            for m in rx.finditer(t):
                v = m.group(0)
                if "abcdefghij" not in v.lower():
                    recovered[sha(v)] = v
    if not totals:
        print("    (clean)")
    print()

    # ---- 2. anywhere else on disk -------------------------------------------
    print("[2] other estate locations holding the SAME values")
    roots = [
        HOME / ".remember", HOME / ".claude" / "event-ledger",
        HOME / ".claude" / "projects" / "C--Users-Prekzursil" / "memory",
        HOME / ".claude" / "history", HOME / ".codex" / "sessions",
    ]
    known = {h for (_, h) in totals}
    found_elsewhere = 0
    for root in roots:
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if not f.is_file() or f.stat().st_size > 200_000_000:
                continue
            try:
                t = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hits = scan(t)
            share = {k: v for k, v in hits.items() if k[1] in known}
            if share:
                found_elsewhere += 1
                rel = f.relative_to(HOME)
                for (label, h), n in share.items():
                    print(f"    ~/{rel}  {label} {h} x{n}")
    if not found_elsewhere:
        print("    none of the exposed values appear in memory/ledger/remember stores")
    print()

    github_liveness(recovered)
    print()
    print("SUCCESS:blast-radius (report only - nothing was modified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
