#!/usr/bin/env python3
"""IMP-0458 canary + mention scenario. Canary values stay in process memory."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

from secret_scrub_gate import (
    report_contains_secret_body,
    scan_tree,
    synthetic_canary_value,
)

HERE = Path(__file__).resolve().parent
MENTION = HERE / "fixtures" / "mention-only"
CLEAN = HERE / "fixtures" / "clean"


def _digest_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def plant_canary_tree(root: Path, canary: str) -> None:
    (root / "receipts").mkdir(parents=True, exist_ok=True)
    (root / "events").mkdir(parents=True, exist_ok=True)
    (root / "staging").mkdir(parents=True, exist_ok=True)
    (root / "receipts" / "planted.json").write_text(
        json.dumps({"id": "canary-receipt", "GITHUB_TOKEN": canary}, indent=1)
        + "\n",
        encoding="utf-8",
    )
    (root / "events" / "planted.jsonl").write_text(
        json.dumps({"event": "artifact-register", "token": canary}) + "\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(root / "staging" / "bundle.zip", "w") as zf:
        zf.writestr("payload.env", f"GITHUB_TOKEN={canary}\n")


def run_canary() -> dict:
    """Plant a synthetic credential in receipt, event and zip. Must fire on all three.

    The returned dict never includes the canary body.
    """
    canary = synthetic_canary_value()
    env_before = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="imp0458-canary-") as tmp:
        root = Path(tmp)
        plant_canary_tree(root, canary)
        before = _digest_tree(root)
        report = scan_tree(root, include=None, exclude=())
        after = _digest_tree(root)
    env_after = dict(os.environ)
    payload = json.dumps(report.to_json(), sort_keys=True)
    leaked = report_contains_secret_body(payload, [canary])
    scopes = [f.scope.replace("\\", "/") for f in report.findings]
    fired_receipt = any("receipts/planted.json" in s for s in scopes)
    fired_event = any("events/planted.jsonl" in s for s in scopes)
    fired_zip = any("staging/bundle.zip::" in s for s in scopes)
    prefixes = sorted({f.prefix for f in report.findings})
    variables = sorted({f.variable for f in report.findings})
    return {
        "fired": fired_receipt and fired_event and fired_zip,
        "fired_receipt": fired_receipt,
        "fired_event": fired_event,
        "fired_packaged": fired_zip,
        "finding_count": len(report.findings),
        "files_examined": report.files_examined,
        "archives_opened": report.archives_opened,
        "prefixes": prefixes,
        "variables": variables,
        "hashes_unchanged": before == after,
        "environ_unchanged": env_before == env_after,
        "report_leaked_body": leaked,
        "byte_length": 40,
        "prefix": "ghp_",
        "mutated": report.mutated,
    }


def run_mention() -> dict:
    report = scan_tree(MENTION, include=None, exclude=())
    return {
        "fired": bool(report.findings),
        "finding_count": len(report.findings),
        "files_examined": report.files_examined,
        "findings": [f.evidence for f in report.findings],
        "opened_paths": report.opened_paths,
    }


def run_clean() -> dict:
    report = scan_tree(CLEAN, include=None, exclude=())
    return {
        "fired": bool(report.findings),
        "finding_count": len(report.findings),
        "files_examined": report.files_examined,
    }
