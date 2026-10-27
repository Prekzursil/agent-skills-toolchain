#!/usr/bin/env python3
"""Both-states control for ci/tests/test_command_doc_promises.py, on REAL bytes.

The in-suite controls use synthetic strings. This probe runs the SAME extraction
and resolution functions the gate uses against the immutable pre-fix BLOB of
``commands/context-budget.md`` and requires the gate to FIRE there.

A probe that is silent in both states measures nothing. This one must print
``broken=1`` for the KNOWN-BROKEN blob and ``broken=0`` for the fixed working
tree, or it exits non-zero.

The blob is pinned by SHA, not by a moving ``HEAD``, so this control keeps its
meaning after the fix is committed.

Run:  python docs/_lane_docs_r4_bothstates.py
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "ci" / "tests" / "test_command_doc_promises.py"

#: The pre-fix state: commands/context-budget.md as committed at 27da3215, whose
#: line 22 reads "Run the **context-budget** skill (`skills/context-budget/SKILL.md`)".
BROKEN_BLOB = "7f62801d0ae052f4e4136122bcd810be023a06ba"


def _load_gate():
    """Import the gate module itself, so this probe exercises the SHIPPED code.

    A missing gate is a HARD failure: silently falling back to a local re-
    implementation is how a control turns into a no-op that agrees with itself.
    (Same reasoning as ``command-center/receipt_validate.py::_load_gate``; that
    one is module-private and hardwired to the receipt-schema gate, so it is not
    importable here -- this is a deliberate second instance, not a missed reuse.)
    """
    if not GATE.is_file():
        raise SystemExit(f"FAILED:docs-r4-bothstates gate absent at {GATE}")
    spec = importlib.util.spec_from_file_location("_r4_gate", GATE)
    if spec is None or spec.loader is None:
        raise SystemExit(f"FAILED:docs-r4-bothstates cannot load {GATE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blob_text(sha: str) -> str:
    out = subprocess.run(
        ["git", "cat-file", "-p", sha],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    # cat-file returns the STORED blob; decode without newline translation.
    return out.decode("utf-8")


def _classify(gate, text: str, tracked) -> list[tuple[int, str, bool]]:
    """Return (line, skill, is_use) for every skill reference in ``text``."""
    found = []
    for match in gate.SKILL_REF.finditer(text):
        sentence = gate._sentence_around(text, match.start(), match.end())
        is_use = not gate._is_mention(sentence)
        line = text[: match.start()].count("\n") + 1
        found.append((line, match.group(1), is_use))
    return found


def main() -> int:
    gate = _load_gate()
    tracked = gate._tracked_paths()
    failures: list[str] = []

    # ---- STATE A: the KNOWN-BROKEN committed blob -------------------------
    broken_text = _blob_text(BROKEN_BLOB)
    broken = [
        (line, skill)
        for line, skill, is_use in _classify(gate, broken_text, tracked)
        if is_use and not gate._resolves(skill, tracked)
    ]
    print(f"STATE A  broken blob {BROKEN_BLOB[:8]}  bytes={len(broken_text)}")
    print(f"         CR bytes={broken_text.count(chr(13))}  (blob is stored LF)")
    for line, skill in broken:
        print(f"         FIRES at line {line} -> skills/{skill}/SKILL.md")
    if len(broken) != 1:
        failures.append(
            f"expected exactly 1 broken promise in the pre-fix blob, got {len(broken)}"
        )
    elif broken[0][1] != "context-budget":
        failures.append(f"fired on the wrong skill: {broken[0][1]}")

    # ---- STATE B: the fixed working tree ----------------------------------
    fixed_path = REPO_ROOT / "commands" / "context-budget.md"
    fixed_text = fixed_path.read_text(encoding="utf-8", newline="")
    classified = _classify(gate, fixed_text, tracked)
    still_broken = [
        (line, skill)
        for line, skill, is_use in classified
        if is_use and not gate._resolves(skill, tracked)
    ]
    mentions = [(line, skill) for line, skill, is_use in classified if not is_use]
    print(f"\nSTATE B  fixed working tree  bytes={len(fixed_text)}")
    print(f"         CRLF={fixed_text.count(chr(13) + chr(10))}")
    print(f"         uses-of-missing={len(still_broken)}  mentions={len(mentions)}")
    if still_broken:
        failures.append(f"the fix did not hold: {still_broken}")
    if len(mentions) != 1:
        failures.append(
            f"expected 1 retirement MENTION in the fixed doc, got {len(mentions)}"
        )

    # ---- The discrimination itself ----------------------------------------
    print("\nDISCRIMINATION")
    print(f"         state A fires : {len(broken)}")
    print(f"         state B fires : {len(still_broken)}")
    if len(broken) == len(still_broken):
        failures.append(
            "the probe returns the SAME verdict in both states -- it is inert "
            "and proves nothing about the gate"
        )

    if failures:
        for f in failures:
            print(f"\nFAILED: {f}")
        print(f"\nFAILED:docs-r4-bothstates violations={len(failures)}")
        return 1
    print(
        f"\nSUCCESS:docs-r4-bothstates broken_state_fires={len(broken)} "
        f"fixed_state_fires={len(still_broken)} mentions_suppressed={len(mentions)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
