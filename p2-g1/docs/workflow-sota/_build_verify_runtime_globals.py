#!/usr/bin/env python3
"""BUILD-lane independent corroboration of the grounding lane's runtime claims.

Mechanically different from the grounding probe: that one dumped fixed byte
OFFSETS (269,022,808 / 267,627,551) and read the surrounding text.  This one does
a content-addressed streaming SUBSTRING COUNT over the whole binary with no
offset knowledge at all, so a wrong offset cannot produce a false agreement.

DETECTOR CONTROL (both-states): a needle that MUST be absent
(``zzz_this_needle_cannot_exist_in_claude_exe``) is counted alongside the real
ones.  If the control comes back non-zero the scanner is broken and no count
here may be cited.

Read-only.  Streams in 8 MiB chunks with an overlap so a needle straddling a
chunk boundary is still found -- the box has ~4.5 GB free and the binary is
287 MB, so it is never loaded whole.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BINARY = Path.home() / ".local" / "bin" / "claude.exe"

NEEDLES: dict[str, bytes] = {
    # the eight injected globals, as the tool-doc block names them
    "doc_pipeline_sig": b"pipeline(items, stage1",
    "doc_default_to_pipeline": b"DEFAULT TO pipeline()",
    "doc_parallel_barrier": b"This is a BARRIER",
    # the two VM context-construction sites that inject the timer pair
    "vm_setTimeout_inject": b"setTimeout:",
    "vm_clearTimeout_inject": b"clearTimeout:",
    "vm_codeGeneration_off": b"codeGeneration:{strings:!1",
    # the shimmed non-determinism
    "shim_date_now": b"Date.now",
    # resume
    "resume_from_run_id": b"resumeFromRunId",
    # DETECTOR CONTROL -- must be 0 or the scanner is broken
    "CONTROL_must_be_zero": b"zzz_this_needle_cannot_exist_in_claude_exe",
}

CHUNK = 8 << 20


def scan(path: Path) -> dict[str, int]:
    counts = {k: 0 for k in NEEDLES}
    overlap = max(len(v) for v in NEEDLES.values()) - 1
    tail = b""
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            window = tail + chunk
            for key, needle in NEEDLES.items():
                counts[key] += window.count(needle)
            tail = window[-overlap:] if overlap else b""
    return counts


def main() -> int:
    if not BINARY.exists():
        print(json.dumps({"error": f"binary not found: {BINARY}"}))
        return 2
    counts = scan(BINARY)
    control_ok = counts["CONTROL_must_be_zero"] == 0
    real = {k: v for k, v in counts.items() if not k.startswith("CONTROL_")}
    verdict = {
        "binary": str(BINARY),
        "size_bytes": BINARY.stat().st_size,
        "counts": counts,
        "detector_control_ok": control_ok,
        "all_real_needles_present": all(v > 0 for v in real.values()),
    }
    print(json.dumps(verdict, indent=2))
    if not control_ok:
        print("FAILED:runtime-globals-probe detector control fired", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
