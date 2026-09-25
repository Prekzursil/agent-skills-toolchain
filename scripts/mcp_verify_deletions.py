"""Independently re-derive the 9 DELETE verdicts.

classify47.py used entry_exists(); this does NOT reuse it. A destructive
recommendation must not rest on one unvalidated helper of my own.
"""
import json
import os
import sys
from shutil import which

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

cfg = json.load(open(r"C:\Users\prekzursil\.claude.json", encoding="utf-8", errors="replace"))
srv = cfg.get("mcpServers") or {}

TARGETS = ["codex", "github_cli", "ocr-suite", "openmm-md", "paper-search",
           "perplexity", "postgres", "rdkit", "sonarqube"]

SEP = ("\\", "/")
print("INDEPENDENT re-derivation of the 9 DELETE candidates")
print("=" * 104)
confirmed, disputed = [], []

for n in TARGETS:
    c = srv.get(n)
    if not isinstance(c, dict):
        print(f"\n{n}: NOT IN CONFIG")
        confirmed.append(n)
        continue
    cmd = c.get("command") or ""
    args = c.get("args") or []
    url = c.get("url") or ""
    print(f"\n{n}:")
    print(f"    command = {cmd!r}")
    print(f"    args    = {args[:5]}")
    if url:
        print(f"    url     = {url}")

    checks, anything_exists = [], False
    if cmd:
        if os.path.isabs(cmd):
            e = os.path.exists(cmd)
            anything_exists |= e
            checks.append(f"abs command exists={e}")
        else:
            w = which(cmd)
            anything_exists |= bool(w)
            checks.append(f"which({cmd}) -> {w}")
    for a in args:
        if isinstance(a, str) and any(s in a for s in SEP) and os.path.isabs(a):
            e = os.path.exists(a)
            anything_exists |= e
            checks.append(f"arg exists={e} :: ...{a[-58:]}")
    for line in checks:
        print(f"    {line}")

    if url and not cmd:
        verdict = "DISPUTED - it is a URL entry, not a missing binary"
        disputed.append(n)
    elif not checks:
        verdict = "DISPUTED - nothing concrete to check; cannot justify deletion"
        disputed.append(n)
    elif anything_exists:
        verdict = "DISPUTED - something DOES exist; classify47 was wrong"
        disputed.append(n)
    else:
        verdict = "CONFIRMED package-gone"
        confirmed.append(n)
    print(f"    => {verdict}")

print("\n" + "=" * 104)
print(f"CONFIRMED deletable ({len(confirmed)}): {confirmed}")
print(f"DISPUTED  ({len(disputed)}): {disputed}")
if disputed:
    print("\n-> classify47.py over-reported. Deletion list is the CONFIRMED set only.")
