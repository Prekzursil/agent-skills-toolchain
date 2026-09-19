#!/usr/bin/env python3
"""Pre-flight harness integrity asserts for the shared MCP control plane.

H3 lane of mcp-harden (2026-09-19). Wired into sync_shared_state.ps1 before any
merge runs. Two asserts, both ledger-proven failure classes:

  1. STALE-PORT BAND: no config surface may reference the dead 314xx/3138x
     cyberstrike band or the pre-2026-09-19 hub ports 8765/8812. (Class: the
     11/19 session-start failures + the 8812->18812 doc family.)
  2. GIT-CRYPT FILTER: the agent-skills-toolchain repo's git-crypt smudge
     filter must not be identity ("cat") — the silent clobber that left
     cloud-hub/search-hub accounts.json ciphertext on disk for weeks.

Exit contract (fail-closed):
  0 = SUCCESS:integrity-clean
  1 = FAILED:integrity <reasons>  (stale ports and/or identity filter)
  2 = FAILED:integrity unreadable/malformed input (never exit 0 on a surface
      we could not read — a missing optional surface is OK, a present-but-
      unreadable one is not)

Env override: INTEGRITY=warn downgrades findings to warnings (exit 0), mirroring
PIN_DRIFT=warn in check_pin_drift.py.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
REPO = HOME / "source" / "agent-skills-toolchain"

# (path, optional?) — optional surfaces may be absent (e.g. ~/.mcp.json retired
# to an empty stub is still checked when present; a future removal is fine).
SURFACES = [
    (HOME / ".agents" / "agents.json", False),
    (HOME / ".claude.json", False),
    (HOME / ".mcp.json", True),
    (HOME / ".gemini" / "settings.json", True),
    (HOME / ".cursor" / "mcp.json", True),
    (HOME / ".config" / "goose" / "config.yaml", True),
    (HOME / ".grok" / "config.toml", True),
    (HOME / ".config" / "opencode" / "opencode.json", True),
]

STALE_RE = re.compile(r"127\.0\.0\.1:31[34]\d\d|127\.0\.0\.1:3138\d|127\.0\.0\.1:8765|127\.0\.0\.1:8812")
# The live band is 311xx; 314xx and 3138x are dead. 8765/8812 are pre-fix hub ports.


def scan_stale_ports() -> list[str]:
    hits: list[str] = []
    for path, optional in SURFACES:
        if not path.exists():
            if optional:
                continue
            hits.append(f"MISSING required surface: {path}")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            hits.append(f"UNREADABLE surface {path}: {exc}")
            continue
        for m in STALE_RE.finditer(text):
            hits.append(f"{path.name}: stale {m.group(0)}")
    return hits


def check_gitcrypt_filter() -> list[str]:
    if not (REPO / ".git").exists():
        return []  # repo absent on this host = nothing to assert
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO), "config", "--get", "filter.git-crypt.smudge"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [f"git-crypt filter probe failed: {exc}"]
    val = (r.stdout or "").strip()
    if r.returncode != 0:
        return []  # filter unset: repo not using git-crypt at all
    if val in ("cat", ""):
        return [f"git-crypt smudge filter is identity ('{val}') in {REPO} — "
                "accounts.json surfaces will check out as ciphertext "
                "(ledger: cloud-hub/search-hub dead for weeks on exactly this)"]
    return []


def main() -> int:
    findings = scan_stale_ports() + check_gitcrypt_filter()
    warn_only = os.environ.get("INTEGRITY", "").lower() == "warn"
    if findings:
        for f in findings:
            print(("WARN: " if warn_only else "VIOLATION: ") + f)
        if warn_only:
            print("SUCCESS:integrity warn-mode (findings above, not blocking)")
            return 0
        print("FAILED:integrity " + f"({len(findings)} finding(s))")
        return 1
    print("SUCCESS:integrity-clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
