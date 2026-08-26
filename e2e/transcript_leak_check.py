#!/usr/bin/env python3
"""Did any LIVE credential actually reach this session's transcript?

The Stop hook reported POTENTIAL-CREDENTIAL on the transcript but deliberately does
not emit the matched value, so its alert alone cannot distinguish a real leak from a
synthetic test fixture. That distinction is the whole question, and it is decidable:
load the real secrets, search the transcript for them, and print ONLY a boolean.

Nothing secret is printed. Every finding is reported as present/absent plus a
sha256[:12] so the owner can correlate without the literal existing anywhere new.

Checks, in order of severity:
  1. the live OPENAI_API_KEY value, and every >=24-char window of it (a partial paste
     is still a leak)
  2. the Codex access_token / refresh_token / id_token values
  3. what credential-SHAPED strings are in the transcript regardless of origin, so the
     synthetic fixtures can be positively identified rather than assumed
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

SESSION_DIR = Path.home() / ".claude" / "projects" / "C--Users-Prekzursil"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def newest_transcript() -> Path | None:
    cands = sorted(SESSION_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime,
                   reverse=True)
    return cands[0] if cands else None


def secrets() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    k = os.environ.get("OPENAI_API_KEY", "").strip()
    if k:
        out.append(("OPENAI_API_KEY", k))
    p = Path.home() / ".codex" / "auth.json"
    if p.exists():
        try:
            tok = (json.loads(p.read_text(encoding="utf-8")).get("tokens") or {})
            for name in ("access_token", "refresh_token", "id_token"):
                v = tok.get(name)
                if isinstance(v, str) and len(v) > 40:
                    out.append((f"codex.{name}", v))
        except Exception:
            pass
    return out


def main() -> int:
    t = newest_transcript()
    if t is None:
        print("FAILED:leak-check no transcript found")
        return 1
    print(f"transcript: {t.name}  ({t.stat().st_size:,} bytes)")
    blob = t.read_text(encoding="utf-8", errors="replace")
    print()

    print("[1] LIVE secret values present in transcript?")
    sec = secrets()
    if not sec:
        print("    (no live secrets loadable - cannot certify; treat as UNKNOWN)")
    leaked = 0
    for name, val in sec:
        full = val in blob
        # a partial paste is still a leak: slide a 24-char window over the entropy body
        partial = any(val[i:i + 24] in blob for i in range(0, max(1, len(val) - 24), 8))
        hit = full or partial
        leaked += bool(hit)
        state = "LEAKED" if hit else "absent"
        print(f"    {state:<7} {name:<22} len={len(val):<5} sha256[:12]={sha(val)}"
              + ("  (partial-window match)" if partial and not full else ""))
    print()

    print("[2] credential-SHAPED strings in the transcript (origin-agnostic)")
    pats = [
        ("OpenAI sk-", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
        ("GitHub ghp_", re.compile(r"\bghp_[A-Za-z0-9]{20,}")),
        ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ]
    for label, rx in pats:
        found = sorted(set(rx.findall(blob)))
        print(f"    {label}: {len(found)} distinct")
        for f in found[:12]:
            # sequential-alphabet bodies are the signature of a synthetic fixture
            synthetic = "abcdefghij" in f.lower() or "0123456" in f
            tag = "SYNTHETIC (sequential-alphabet body)" if synthetic else "!! REVIEW"
            print(f"      {tag:<38} len={len(f):<4} sha256[:12]={sha(f)}")
    print()

    print("[3] verdict")
    if leaked:
        print("    FAILED:leak-check a LIVE credential value is present -> ROTATE IT")
        return 1
    print("    no live credential value found in the transcript")
    print("    SUCCESS:leak-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
