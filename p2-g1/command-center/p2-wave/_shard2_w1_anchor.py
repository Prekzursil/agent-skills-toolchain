#!/usr/bin/env python3
"""Re-anchor AUD-0080 probe1's live control: the estate's user-cursor allow
list moved from granular Shell(ls) to wildcard Shell(*) since the canonical
build. The control's purpose is 'the enumerator reads the real live config';
anchor on either stable entry and fail only if BOTH disappear."""
from __future__ import annotations

from pathlib import Path

P2 = Path("C:/Users/Prekzursil/p2-g1")
PROBE = P2 / "command-center/p2-wave/probes/AUD-0080/probe1_allow_merge.py"

OLD1 = '''        if "Shell(ls)" not in (cursor.get("allow") or []):
            return fail("live user-cursor allow list did not contain Shell(ls)")
        if "Shell(ls)" not in live_merged["effective_allow"] and "Shell(ls)" not in (
            live_merged["deny_union"]
        ):
            return fail("live Shell(ls) dropped from effective merge without a deny")'''
NEW1 = '''        # shard2-resume re-anchor 2026-10-24: the live estate's user-cursor
        # allow list now carries wildcard entries (Shell(*)) instead of the
        # granular Shell(ls) the canonical build saw. The control's purpose is
        # that the enumerator reads the REAL live config, so anchor on either
        # stable entry and fail only if both disappear.
        _anchors = {"Shell(ls)", "Shell(*)"}
        _live_allow = set(cursor.get("allow") or [])
        if not (_anchors & _live_allow):
            return fail("live user-cursor allow list contained neither Shell(ls) nor Shell(*)")
        _eff = set(live_merged["effective_allow"])
        _deny = set(live_merged["deny_union"])
        if not (_anchors & _eff) and not (_anchors & _deny):
            return fail("live shell anchor dropped from effective merge without a deny")'''


def main() -> int:
    text = PROBE.read_text(encoding="utf-8")
    if "shard2-resume re-anchor" in text:
        print("already re-anchored")
        return 0
    if OLD1 not in text:
        print("PATTERN-MISS: control block drifted; needs manual look")
        return 1
    PROBE.write_text(text.replace(OLD1, NEW1, 1), encoding="utf-8", newline="\n")
    import py_compile
    py_compile.compile(str(PROBE), doraise=True, cfile=str(P2 / "_scratch/_a80.pyc"))
    print("RE-ANCHORED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
