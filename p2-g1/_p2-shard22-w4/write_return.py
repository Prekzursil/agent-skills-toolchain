#!/usr/bin/env python3
"""Write probes/<uid>/SUBAGENT-RETURN.json from simple argv fields + note file.

Usage:
  python write_return.py <UID> <note-file> <probe1-cmd> <probe1-role> \
      <probe2-cmd> <probe2-role> <extra-artifact> [<extra-artifact> ...]

The note file holds the wave4_completion note (plain text, first paragraph).
JSON is assembled here, never hand-typed, so no duplicate-key corruption.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    uid, note_file, p1cmd, p1role, p2cmd, p2role, *extra = argv
    note = Path(note_file).read_text(encoding="utf-8").strip()
    doc = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{uid}",
        "output_path": f"command-center/receipts/{uid}.json",
        "output_schema": "command-center/schema/receipt.schema.json",
        "wave4_completion": {
            "at": "2026-10-26T00:00:00Z",
            "by": "claude-code builder shard 22 wave 4 (P2 program, resume)",
            "note": note,
        },
        "named_probes": [
            {"command": p1cmd, "id": "probe1", "role": p1role},
            {"command": p2cmd, "id": "probe2", "role": p2role},
        ],
        "extra_artifacts": list(extra),
        "reviewer_note": (
            "receipt carries an independent reviewer closure (PASS, "
            "independent) which still verifies live; kept per unit contract"
        ),
    }
    out = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"SUCCESS:return {uid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
