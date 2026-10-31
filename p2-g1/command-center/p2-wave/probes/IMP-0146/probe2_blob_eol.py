#!/usr/bin/env python3
"""IMP-0146 probe2: a CRLF working-tree copy and an LF blob copy of the SAME
canonical export both parse back to the same value (EOL-insensitive import)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

import agentspec.canonical as C  # noqa: E402

DOC = {
    "kind": "Workflow",
    "id": "eol-twin",
    "nodes": [
        {"kind": "WorkUnit", "id": "a", "prompt": "p", "timeout_s": 30,
         "receipt": {"fmt": "json", "required_fields": ["r"]}},
        {"kind": "FanOut", "id": "f", "unit_ids": ["a", "b"]},
    ],
}


def main() -> int:
    blob = C.export(DOC)                      # LF bytes
    crlf = blob.replace(b"\n", b"\r\n")       # working-tree twin

    v_lf = C.loadb(blob)
    v_crlf = C.loadb(crlf)
    same_value = C.export(v_lf) == C.export(v_crlf)

    # and both re-export to the canonical LF form byte-identically
    re_export_lf = C.export(C.loadb(crlf)) == blob
    re_export_crlf = C.export(C.loadb(blob)) == blob

    result = {
        "unit_id": "IMP-0146",
        "probe": "probe2-blob-eol",
        "blob_bytes": len(blob),
        "crlf_twin_bytes": len(crlf),
        "same_value": same_value,
        "crlf_reexports_to_blob": re_export_lf,
        "lf_reexports_to_blob": re_export_crlf,
        "pass": same_value and re_export_lf and re_export_crlf,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0146-probe2 CRLF working-tree and LF blob twins both round trip"
            if result["pass"] else
            "FAILED:IMP-0146-probe2 EOL-insensitive import broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
