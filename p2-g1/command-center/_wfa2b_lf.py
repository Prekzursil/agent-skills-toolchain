"""Normalize this unit's artifacts to LF, matching sibling platform/ artifacts (CRLF=0).

Reads bytes, replaces CRLF with LF, writes bytes back with newline='' semantics
(binary write), so no platform translation re-inserts CR. Prints a before/after
count per file -- a fixer that does not measure its own effect is not a fixer.
"""

from __future__ import annotations

from pathlib import Path

CRLF = b"\r\n"
LF = b"\n"

FILES = [
    "command-center/_wfa2b_probe.py",
    "command-center/_wfa2b_build_registry.py",
    "command-center/_wfa2b_verify.py",
    "command-center/_wfa2_enumerate.py",
    "command-center/_wfa2b_lf.py",
    "platform/registry/workflow-candidates-2.json",
]
REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")


def main() -> int:
    changed = 0
    for rel in FILES:
        p = REPO / rel
        if not p.exists():
            print(f"  ABSENT  {rel}")
            continue
        raw = p.read_bytes()
        before = raw.count(CRLF)
        if before:
            p.write_bytes(raw.replace(CRLF, LF))
            changed += 1
        after = p.read_bytes().count(CRLF)
        print(f"  {rel}: CRLF {before} -> {after}")
        if after:
            print(f"FAILED:lf-normalize {rel} still has {after} CRLF")
            return 1
    print(f"SUCCESS:lf-normalize {changed} file(s) rewritten, all now CRLF=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
