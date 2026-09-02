#!/usr/bin/env python3
"""Mock workers for ADV-0003. Every kind exits 0. Kind selects the write.

missing:          write nothing
case-miss:        write Output.json, receipt claims output.json
trailing-space:   write 'output.json ' (trailing space), receipt claims output.json
backslash:        write a file whose name contains a backslash, receipt claims output.json
valid:            write output.json and a matching receipt (detector control)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

EXPECTED_ARTIFACT = "output.json"
EXPECTED_RECEIPT = "receipt.json"
CONTROL_SENTINEL = "SUCCESS:ADV-0003-CONTROL"


def sha256_lf(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def write_receipt(root: Path, artifact_rel: str, sha: str) -> None:
    doc = {
        "unit_id": "ADV-0003-CONTROL",
        "state": "SUCCESS",
        "sentinel": CONTROL_SENTINEL,
        "exit_code": 0,
        "artifacts": [{"path": artifact_rel, "sha256": sha}],
    }
    (root / EXPECTED_RECEIPT).write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    kind = os.environ.get("ADV0003_KIND") or (sys.argv[1] if len(sys.argv) > 1 else "")
    root = Path(os.environ.get("ADV0003_ROOT") or (sys.argv[2] if len(sys.argv) > 2 else "."))
    root.mkdir(parents=True, exist_ok=True)
    payload = b'{"ok": true, "marker": "ADV-0003-worker"}\n'
    sha = sha256_lf(payload)

    if kind == "missing":
        pass
    elif kind == "case-miss":
        (root / "Output.json").write_bytes(payload)
        write_receipt(root, EXPECTED_ARTIFACT, sha)
    elif kind == "trailing-space":
        (root / (EXPECTED_ARTIFACT + " ")).write_bytes(payload)
        write_receipt(root, EXPECTED_ARTIFACT, sha)
    elif kind == "backslash":
        (root / "output\\json").write_bytes(payload)
        write_receipt(root, EXPECTED_ARTIFACT, sha)
    elif kind == "valid":
        (root / EXPECTED_ARTIFACT).write_bytes(payload)
        write_receipt(root, EXPECTED_ARTIFACT, sha)
    else:
        sys.stderr.write(f"unknown worker kind: {kind!r}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
