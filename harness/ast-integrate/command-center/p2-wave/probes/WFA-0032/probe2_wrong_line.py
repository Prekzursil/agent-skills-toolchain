#!/usr/bin/env python3
"""Probe 2: wrong line number is caught by content-hash comparison (both states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from corpus import ANCHOR_LINE, WRONG_LINE  # noqa: E402
from deref import deref_filesystem, sha256_bytes  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0032-extract-provenance.json"


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0032-probe2 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file():
        return _fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    recs = [r for r in (doc.get("records") or []) if r.get("status") == "RESOLVED"]
    if not recs:
        return _fail("no RESOLVED records to mutate")
    rec = recs[0]
    path = REPO / rec["anchor"]["path"]
    stored = rec.get("line_sha256")
    if not stored or len(stored) != 64:
        return _fail("stored line_sha256 missing")
    good = deref_filesystem(path, ANCHOR_LINE)
    bad = deref_filesystem(path, WRONG_LINE)
    if not good.get("ok") or not bad.get("ok"):
        return _fail("could not read good/bad lines")
    if good["line_sha256"] != stored:
        return _fail("good-state line hash does not match stored hash")
    if bad["line_sha256"] == stored:
        return _fail("wrong line was NOT caught (hashes match stored anchor)")
    if good["line_sha256"] == bad["line_sha256"]:
        return _fail("good and wrong lines are identical; detector is vacuous")
    ctrl = doc.get("wrong_line_control") or {}
    if not ctrl.get("caught"):
        return _fail("artifact wrong_line_control.caught is not true")
    if ctrl.get("correct_line_sha256") != stored and rec["candidate_id"] == ctrl.get(
        "candidate_id"
    ):
        return _fail("control hash disagrees with record")
    out = {
        "probe": "probe2-wrong-line",
        "candidate_id": rec["candidate_id"],
        "good_line": ANCHOR_LINE,
        "wrong_line": WRONG_LINE,
        "stored_line_sha256": stored,
        "good_line_sha256": good["line_sha256"],
        "wrong_line_sha256": bad["line_sha256"],
        "good_state_matches": True,
        "wrong_line_caught": True,
        "file_sha256": rec.get("content_sha256"),
        "file_sha256_recomputed": sha256_bytes(path.read_bytes()),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:WFA-0032-probe2 wrong line number caught by content-hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
