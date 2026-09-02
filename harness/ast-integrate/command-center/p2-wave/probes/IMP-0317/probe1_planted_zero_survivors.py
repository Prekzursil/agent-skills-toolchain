#!/usr/bin/env python3
"""Probe 1: planted-secret corpus, redactor ON, zero survivors.

Live persist through tools/council/artifacts/retention.py, then:
  (1) exact-body survivor check across all 4 encodings (must be 0)
  (2) independent gitleaks-style scan of the same artifact directory (must be 0
      findings that still carry a planted body)

Both-states is probe 2 (redactor disabled). This probe is the good state.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.artifacts.retention import (  # noqa: E402
    RetentionPolicy,
    persist_transcript,
)
import corpus as C  # noqa: E402
import gitleaks_style as G  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0317.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0317-probe1 {msg}")
    return 1


def main() -> int:
    policy = RetentionPolicy(redact=True, refuse_if_survivors=True)
    with tempfile.TemporaryDirectory(prefix="imp0317-p1-") as td:
        dest = Path(td) / "council" / "transcript.json"
        meta = persist_transcript(C.transcript(), dest, policy)
        data = dest.read_bytes()
        survivors = C.survivor_kinds(data)
        gl = G.scan_dir(dest.parent)

        print(
            json.dumps(
                {
                    "probe": "probe1-planted-zero-survivors",
                    "unit_id": "IMP-0317",
                    "bytes": meta["bytes"],
                    "redaction_applied": meta["redaction_applied"],
                    "survivor_kinds": survivors,
                    "survivor_count": len(survivors),
                    "gitleaks_hits": len(gl),
                    "encodings_checked": list(C.ENCODINGS),
                },
                sort_keys=True,
            )
        )
        if not meta["redaction_applied"]:
            return fail("redaction_applied is false on the shipped persist path")
        if survivors:
            return fail(f"survivors in persisted artifact: {survivors}")
        if gl:
            return fail(f"gitleaks-style scan fired on redacted artifact: {gl}")
        if not dest.is_file() or dest.stat().st_size <= 0:
            return fail("persisted artifact missing")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0317" not in text:
        return fail("sentinel-absent")
    ev = doc.get("evidence") or []
    if not isinstance(ev, list) or len(ev) < 2:
        return fail("evidence[] missing two independent signals")
    zero = False
    for item in ev:
        if isinstance(item, dict) and item.get("id") == "planted-secret-corpus":
            if item.get("survivors") == 0:
                zero = True
    if not zero:
        return fail("receipt does not record 0 survivors for planted-secret-corpus")
    print("SUCCESS:IMP-0317-probe1 planted corpus zero survivors under redactor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
