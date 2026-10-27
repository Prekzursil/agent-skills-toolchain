"""Calibrate the C5 content floor against the TEN REAL receipts before inventing a threshold.

A floor chosen from intuition false-positives on a terse-but-valid review; the grounding round
flagged exactly that as the unproven part of the plan [likely, 55-80%]. So measure the real
distribution first, then pick a threshold with margin under the observed minimum.

Reads COMMITTED blobs (the basis CI runs on), never the contended worktree.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "_vs_cal", Path(__file__).with_name("vendor_satisfiability.py")
)
_vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vs)

# claim_gate's own anchor shape, reused rather than re-invented.
_ANCHOR = re.compile(r"https?://\S+|\S+:\d+")
# A file:line anchor whose file half looks like a repo path we can try to resolve.
_FILE_LINE = re.compile(r"([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,6}):(\d+)")


def main() -> int:
    rows = [r for r in _vs.load_units("committed") if r["verdict"] == _vs.SAT]
    blobs = _vs.batch_blobs("HEAD", [r["output_path"] for r in rows])
    print(f"satisfiable rows: {len(rows)}")
    print(
        f"{'unit':<10} {'notes':>6} {'anchors':>7} {'resolve':>7} "
        f"{'falsif':>6}  reviewer keys"
    )
    lengths, anchor_counts, resolved_counts = [], [], []
    falsif_hits = 0
    all_keys: set[str] = set()
    for r in rows:
        rec = json.loads(blobs[r["output_path"]])
        rv = rec.get("reviewer") or {}
        all_keys |= set(rv)
        notes = rv.get("notes")
        notes = notes if isinstance(notes, str) else json.dumps(notes)
        anchors = _ANCHOR.findall(notes)
        resolved = 0
        for path, _line in _FILE_LINE.findall(notes):
            if (REPO / path.replace("\\", "/")).exists():
                resolved += 1
        falsif = bool(
            re.search(
                r"falsif|refut|mutat|counter-?example|tried to break|both[- ]states"
                r"|control|disconfirm|negative case",
                notes,
                re.I,
            )
        )
        falsif_hits += falsif
        lengths.append(len(notes))
        anchor_counts.append(len(anchors))
        resolved_counts.append(resolved)
        print(
            f"{r['id']:<10} {len(notes):>6} {len(anchors):>7} {resolved:>7} "
            f"{'yes' if falsif else 'NO':>6}  {sorted(rv)}"
        )
    print()
    print(f"notes chars   : min={min(lengths)} max={max(lengths)}")
    print(f"anchors/unit  : min={min(anchor_counts)} max={max(anchor_counts)}")
    print(f"RESOLVING     : min={min(resolved_counts)} max={max(resolved_counts)}")
    print(f"falsification language present: {falsif_hits}/{len(rows)}")
    print(f"union of reviewer keys: {sorted(all_keys)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
