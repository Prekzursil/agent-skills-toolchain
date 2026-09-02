#!/usr/bin/env python3
"""Named probe 2: self-scan the receipt; tooling errors are NOT-CHECKED.

A scanner exit that is not a completed clean run must never be read as
CLEAN. Independent of probe 1's canary plant.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.release.bundle_secret_scan import (  # noqa: E402
    EXIT_TOOLING,
    SCANNER_NAME,
    classify_nonzero_as_clean,
    classify_scan_status,
    scan_extracted,
)

ART = REPO / "command-center/receipts/REL-0010.json"
SCANNER = REPO / "tools/release/bundle_secret_scan.py"

# Patterns that would mean the reporter leaked credential material into itself.
# These are format markers, not live secrets.
LEAK_MARKERS = (
    "-----BEGIN ",
    "AKIA",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "eyJ",
)


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:REL-0010-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:REL-0010" not in text:
        return _fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared:{doc.get('state')}")

    for marker in LEAK_MARKERS:
        if marker in text:
            return _fail("receipt contains credential-shaped material", {"marker": marker})

    findings = doc.get("evidence", {}).get("canary_control", {}).get("findings") or []
    for row in findings:
        if not isinstance(row, dict):
            return _fail("finding is not an object")
        for banned in ("value", "secret", "token", "raw", "match", "body"):
            if banned in row:
                return _fail("finding carries a value field", {"banned": banned})
        required = ("variable_name", "containing_path", "byte_length", "authenticates")
        missing = [k for k in required if k not in row]
        if missing:
            return _fail("finding missing required redacted fields", missing)

    with tempfile.TemporaryDirectory(prefix="rel0010-probe2-self-") as tmp:
        bundle = Path(tmp) / "receipt-bundle"
        bundle.mkdir()
        shutil.copy2(ART, bundle / "REL-0010.json")
        self_scan = scan_extracted(bundle)
    if not self_scan.completed:
        return _fail("self-scan tooling-error", self_scan.to_dict())
    if self_scan.findings:
        return _fail(
            "self-scan found credential material in the receipt",
            [f.to_dict() for f in self_scan.findings],
        )
    if self_scan.files_examined < 1:
        return _fail("self-scan examined nothing")

    missing_root = Path("/tmp/rel0010-no-such-extracted-root")
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCANNER),
            "--extracted-root",
            str(missing_root),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**dict(**__import__("os").environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if proc.returncode == 0:
        return _fail("missing-root scan exited 0 (looks like a clean result)")
    status = classify_scan_status(proc.returncode)
    if status != "NOT-CHECKED":
        return _fail(
            "tooling error was not classified NOT-CHECKED",
            {"returncode": proc.returncode, "status": status},
        )
    if proc.returncode != EXIT_TOOLING:
        return _fail("expected tooling exit 1", {"returncode": proc.returncode})
    mutant = classify_nonzero_as_clean(proc.returncode)
    if mutant == "CLEAN" and status == "NOT-CHECKED":
        mutant_rejected = True
    else:
        return _fail("nonzero-as-clean mutant did not disagree with the real classifier")

    stored_self = doc.get("evidence", {}).get("self_scan", {})
    if stored_self.get("findings_count") != 0:
        return _fail("receipt self_scan findings_count is not zero", stored_self)
    if doc.get("scanner", {}).get("name") != SCANNER_NAME:
        return _fail("scanner name drifted")

    payload = {
        "pass": True,
        "probe": "probe2-selfscan-and-tooling",
        "unit_id": "REL-0010",
        "self_scan_findings": 0,
        "self_scan_files_examined": self_scan.files_examined,
        "tooling_exit": proc.returncode,
        "tooling_status": status,
        "nonzero_as_clean_mutant": mutant,
        "mutant_rejected": mutant_rejected,
        "leak_markers_absent": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"self_scan_findings=0 tooling_status={status} "
        f"mutant_rejected={mutant_rejected}"
    )
    print("SUCCESS:REL-0010-probe2 self-scan and tooling-error NOT-CHECKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
