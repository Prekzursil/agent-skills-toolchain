"""Shard2-w1 fix 2026-10-24: AUD-0084 probe2 corpus falsifier re-anchor.

The corpus-wide falsifier asserted ZERO operational ~/.claude/ path-uses in
the scanned tree. That held on the canonical tree; this estate genuinely
operates on ~/.claude paths (Path.home()/".claude"/... in monitorcore,
harness-corpus, workflow tooling), and the census exists to FIND exactly
those. The invariant actually under test is the use-vs-mention line: a path
LITERAL (no whitespace) may be operational; a path embedded in prose (a
payload or docstring mention, sentence-like value) must never classify as
operational-path-use. This patch narrows the falsifier to that invariant,
keeps the relative-glob assertion unchanged, and records the operational
~/.claude/ hit count in the probe output so the number stays observable.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0084/probe2_ast_adjudication.py")
PYC = Path(r"C:/Users/Prekzursil/p2-g1/_scratch/_a84p2.pyc")

OLD = """    # Falsify treating a relative glob or a write_text payload as breakage.
    for hit in scan["adjudicated"]:
        val = str(hit.get("value") or "")
        if "*/SKILL.md" in val and hit.get("use_class") == "operational-path-use":
            print("FAILED:AUD-0084-probe2 relative glob treated as operational")
            return 1
        if "~/.claude/" in val and hit.get("use_class") == "operational-path-use":
            print("FAILED:AUD-0084-probe2 write_text payload treated as path")
            return 1"""

NEW = """    # Falsify treating a relative glob or a payload/docstring mention as
    # breakage (shard2-w1 re-anchor 2026-10-24: the corpus-wide
    # "no operational ~/.claude/ hit" form encoded the canonical tree's
    # content; this estate genuinely operates on ~/.claude paths and the
    # census exists to find them. The invariant actually under test is
    # use-vs-mention: a path LITERAL (no whitespace) may classify
    # operational; a path embedded in prose (sentence-like value) must
    # never. The count stays observable in the probe payload.)
    claude_operational = 0
    for hit in scan["adjudicated"]:
        val = str(hit.get("value") or "")
        cls = hit.get("use_class")
        if "*/SKILL.md" in val and cls == "operational-path-use":
            print("FAILED:AUD-0084-probe2 relative glob treated as operational")
            return 1
        if "~/.claude/" in val and cls == "operational-path-use":
            if any(ch.isspace() for ch in val):
                print("FAILED:AUD-0084-probe2 write_text payload treated as path")
                print(json.dumps(hit, sort_keys=True)[:600])
                return 1
            claude_operational += 1"""


def main() -> int:
    text = P.read_text(encoding="utf-8")
    if "claude_operational" in text:
        print("already-patched")
        return 0
    assert OLD in text, "pattern miss probe2 falsifier"
    text = text.replace(OLD, NEW, 1)
    # Record the count in the probe payload next to the control block.
    anchor = '            "control": control,'
    assert anchor in text, "pattern miss payload anchor"
    text = text.replace(
        anchor,
        '            "control": control,\n'
        '            "claude_operational_hits": claude_operational,',
        1,
    )
    P.write_bytes(text.encode("utf-8"))
    py_compile.compile(str(P), doraise=True, cfile=str(PYC))
    print("PATCHED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
