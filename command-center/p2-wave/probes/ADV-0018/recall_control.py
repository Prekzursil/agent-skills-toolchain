"""ADV-0018 recall control: prove the vault is mounted and the topic lane is reachable.

RED when the vault is absent (the 2026-08-19 Linux state), GREEN when the walk finds
the known-present program notes BEFORE any absence is reported. A probe that can only
go green cannot detect a missing substrate, so the absent-vault branch is exercised
as the documented bad state.
"""

from __future__ import annotations

import json
import sys

from shared import VAULT, retrieve_topic_notes, write_raw


def main() -> int:
    if not VAULT.is_dir():
        msg = "RED: vault absent at " + str(VAULT)
        print(msg)
        write_raw("recall-control", {"verdict": "RED", "reason": msg, "notes": []}, msg + "\n")
        return 1
    notes = retrieve_topic_notes()
    if not notes:
        msg = "RED: vault present but topic retrieval returned 0 notes"
        print(msg)
        write_raw("recall-control", {"verdict": "RED", "reason": msg, "notes": []}, msg + "\n")
        return 1
    total = sum(1 for _ in VAULT.rglob("*.md"))
    names = [str(n) for n in notes]
    msg = (
        f"GREEN: vault mounted at {VAULT}; {total} md notes walked; "
        f"topic retrieval found {len(notes)} program-subject notes BEFORE any absence check"
    )
    print(msg)
    for n in names:
        print("  hit:", n)
    write_raw("recall-control", {
        "verdict": "GREEN", "reason": msg, "total_md": total,
        "notes": names,
    }, msg + "\n" + "\n".join("  hit: " + n for n in names) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
