#!/usr/bin/env python3
"""stable_prefix_lint.py - KV-cache stable-prefix hygiene lint (REPORT ONLY).

The prompt-cache only pays off when the always-on prefix is byte-identical turn to
turn. Any always-on FILE that carries per-turn-varying content (a regeneration
timestamp, a clock time, a PID, a monotonic counter) changes the prefix bytes and
forces a cold re-encode of the whole prefix - the exact cost cache_lens.py measures.

This lint enumerates the always-on memory files (the CLAUDE.md roots and every file
they @-import, resolved recursively), reports each file's byte size, and flags any
whose CONTENT contains volatile markers that would break the cached prefix. It also
flags DANGLING @-imports (a reference to a file that does not exist).

It changes nothing - it does not touch hooks, settings, or any file. A bare calendar
date (YYYY-MM-DD, no time) is treated as static doc content and only counted, never
flagged: these governance docs are full of "verified 2026-09-25" lines that do NOT
vary per turn. The flag fires only on strong regeneration signals (date+TIME, clock
time, explicit generated/updated-at markers, PIDs, epoch seconds).

Caveat (honest scope): a single read cannot PROVE per-turn variance; this is a
content-pattern heuristic. Two reads across turns would prove it. Volatility that
lives in HOOK OUTPUT (SessionStart/UserPromptSubmit injection) is out of scope here -
this lint audits FILES, which is what the lane asks for.

Both-states proof: --selftest feeds one fixture WITH a regeneration timestamp (must be
FLAGGED) and one WITHOUT (must be CLEAN); a lint silent on both would fail.
"""
from __future__ import annotations

import argparse
import os
import re
import tempfile

HOME = os.path.expanduser("~")
DEFAULT_ROOTS = [
    os.path.join(HOME, ".claude", "CLAUDE.md"),
    os.path.join(HOME, "CLAUDE.md"),
]

_IMPORT = re.compile(r"^@(\S+)")

# Strong per-turn-varying signals (would break the cached prefix if regenerated):
_VOLATILE = [
    ("datetime", re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?\b")),
    ("clock-time", re.compile(r"(?<!\d)\d{1,2}:\d{2}:\d{2}(?!\d)")),
    ("gen-marker", re.compile(r"(?i)\b(generated(?: at| on)?|last[- ]updated|updated at|as of now|timestamp\s*[:=]|run\s*#\s*\d|pid\s*[:=]\s*\d|epoch\s*[:=])")),
    ("epoch-secs", re.compile(r"(?<!\d)1[0-9]{9}(?!\d)")),
]
# Low-signal (static doc content) - counted, not flagged:
_BARE_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?![\d T])")


def resolve_imports(roots):
    """Return (ordered_files, dangling) by following @-imports recursively.

    ordered_files: list of (path, exists_bool). dangling: list of (importer, ref).
    """
    ordered = []
    dangling = []
    seen = set()
    stack = list(roots)
    # Track which file referenced what, for dangling reports
    origin = {os.path.abspath(r): "(root)" for r in roots}
    while stack:
        raw = stack.pop(0)
        ap = os.path.abspath(raw)
        if ap in seen:
            continue
        seen.add(ap)
        exists = os.path.isfile(ap)
        ordered.append((ap, exists))
        if not exists:
            dangling.append((origin.get(ap, "?"), ap))
            continue
        try:
            with open(ap, encoding="utf-8") as f:
                text = f.read()
        except Exception:
            continue
        base = os.path.dirname(ap)
        for line in text.splitlines():
            m = _IMPORT.match(line.strip())
            if not m:
                continue
            ref = m.group(1)
            target = ref if os.path.isabs(ref) or re.match(r"^[A-Za-z]:", ref) else os.path.join(base, ref)
            tap = os.path.abspath(target)
            origin.setdefault(tap, ap)
            if tap not in seen:
                stack.append(target)
    return ordered, dangling


def scan_volatile(path: str):
    """Return (flagged_bool, hits, bare_date_count)."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return False, [], 0
    hits = []
    for label, rx in _VOLATILE:
        found = rx.findall(text)
        if found:
            sample = found[0] if isinstance(found[0], str) else str(found[0])
            hits.append((label, len(found), sample[:32]))
    bare = len(_BARE_DATE.findall(text))
    return (len(hits) > 0), hits, bare


def run_selftest() -> int:
    tmp = tempfile.mkdtemp(prefix="prefix_lint_selftest_")
    vol = os.path.join(tmp, "volatile.md")
    with open(vol, "w", encoding="utf-8") as f:
        f.write("# Status\nGenerated at 2026-09-25T14:03:22 by the daemon.\npid: 48213\n")
    stable = os.path.join(tmp, "stable.md")
    with open(stable, "w", encoding="utf-8") as f:
        f.write("# Contract\nVerified 2026-09-25 against the docs. Rule 2 mandates X.\n")

    fv, hv, _ = scan_volatile(vol)
    fs, hs, bs = scan_volatile(stable)

    checks = []
    ok = True
    c1 = (fv is True and len(hv) >= 1)
    checks.append(f"  volatile fixture FLAGGED     : {fv}  hits={[h[0] for h in hv]}  {'OK' if c1 else 'FAIL'}")
    ok &= c1
    c2 = (fs is False)
    checks.append(f"  stable fixture CLEAN         : flagged={fs} (bare-dates={bs}, not flagged)  {'OK' if c2 else 'FAIL'}")
    ok &= c2

    # dangling-import both-states: one real root + one @-import to a missing file
    root = os.path.join(tmp, "root.md")
    with open(root, "w", encoding="utf-8") as f:
        f.write("# Root\n@stable.md\n@does_not_exist.md\n")
    ordered, dangling = resolve_imports([root])
    c3 = any(d[1].endswith("does_not_exist.md") for d in dangling)
    checks.append(f"  dangling @-import detected    : {[os.path.basename(d[1]) for d in dangling]}  {'OK' if c3 else 'FAIL'}")
    ok &= c3
    c4 = any(p.endswith("stable.md") and ex for p, ex in ordered)
    checks.append(f"  valid @-import resolved       : {c4}  {'OK' if c4 else 'FAIL'}")
    ok &= c4

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print("SELF-TEST (volatile-content + dangling-import both-states proof):")
    print("\n".join(checks))
    if ok:
        print("\nSUCCESS:stable_prefix_lint_selftest")
        return 0
    print("\nFAILED:stable_prefix_lint_selftest one or more assertions failed")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="always-on stable-prefix (KV-cache) lint - report only")
    ap.add_argument("--root", action="append", default=None,
                    help="always-on memory root (repeatable); default ~/.claude/CLAUDE.md + ~/CLAUDE.md")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()

    roots = args.root or DEFAULT_ROOTS
    ordered, dangling = resolve_imports(roots)

    print("STABLE-PREFIX LINT (always-on memory files) - REPORT ONLY")
    print(f"  roots: {roots}\n")
    print(f"{'file':60} {'bytes':>8}  {'stable?':8} notes")
    total = 0
    flagged_files = []
    for path, exists in ordered:
        short = path.replace(HOME, "~")
        if not exists:
            print(f"{short:60} {'MISSING':>8}  {'DANGLING':8} @-import target does not exist")
            continue
        nbytes = os.path.getsize(path)
        total += nbytes
        flagged, hits, bare = scan_volatile(path)
        if flagged:
            flagged_files.append((short, hits))
            note = "PER-TURN-VARYING: " + ", ".join(f"{lbl}x{n}" for lbl, n, _ in hits)
            verdict = "UNSTABLE"
        else:
            note = f"static ({bare} bare dates, not cache-breaking)"
            verdict = "stable"
        print(f"{short:60} {nbytes:>8,}  {verdict:8} {note}")

    print(f"\n  total always-on file bytes : {total:,}  (~{int(total/4):,} tokens @4 chars/tok)")
    print(f"  files enumerated           : {len(ordered)}  ({sum(1 for _, e in ordered if e)} present, "
          f"{sum(1 for _, e in ordered if not e)} dangling)")

    print("\n-- VERDICT --")
    if flagged_files:
        print(f"  {len(flagged_files)} always-on file(s) carry per-turn-varying content that WOULD break the")
        print("  cached prefix on regeneration:")
        for short, hits in flagged_files:
            print(f"    {short}: {', '.join(lbl for lbl, _, _ in hits)}")
    else:
        print("  No always-on FILE carries per-turn-varying content. The file-prefix is stable;")
        print("  any prefix-cache thrash (see cache_lens.py) comes from tool-def/order changes,")
        print("  model/thinking swaps, or HOOK output injection - NOT from these files.")
    if dangling:
        print(f"\n  {len(dangling)} DANGLING @-import(s) (prefix hygiene, not cache-breaking):")
        for importer, ref in dangling:
            print(f"    {ref.replace(HOME, '~')}  (referenced by {importer.replace(HOME, '~') if importer!='(root)' else 'a root'})")

    print("\nSUCCESS:stable_prefix_lint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
