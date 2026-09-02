#!/usr/bin/env python3
"""EOL control and no-write control for ADV-0017."""
from __future__ import annotations

from pathlib import Path

from lib_classify import classify, decode
from scope_guard import no_write_report, tree_fingerprint


def eol_control(repo_root: Path, live_root: Path, eol_rel: str) -> dict:
    rp = repo_root / eol_rel
    lp = live_root / eol_rel
    if not rp.is_file() or not lp.is_file():
        return {
            "id": "eol-control",
            "path": eol_rel,
            "result": "FAIL",
            "pass": False,
            "note": "EOL control file missing",
        }
    rb, lb = rp.read_bytes(), lp.read_bytes()
    kind = classify(decode(rb), decode(lb))
    bytes_differ = rb != lb
    ok = kind in {"BYTE-IDENTICAL-LF", "EOL-ONLY"} and bytes_differ
    return {
        "id": "eol-control",
        "path": eol_rel,
        "classification": kind,
        "bytes_differ": bytes_differ,
        "repo_has_crlf": b"\r\n" in rb,
        "live_has_crlf": b"\r\n" in lb,
        "pass": ok,
        "result": "PASS" if ok else "FAIL",
        "note": (
            "A file known to differ ONLY by line endings must classify as "
            "identical after LF normalisation. Content divergence here would "
            "inflate every count in the artifact."
        ),
    }


def snapshot(repo_root: Path, live_root: Path) -> dict:
    return {
        "repo": tree_fingerprint(repo_root),
        "live": tree_fingerprint(live_root),
    }


def finish_no_write(repo_root: Path, live_root: Path, before: dict) -> dict:
    after = snapshot(repo_root, live_root)
    merged_before = {f"repo:{k}": v for k, v in before["repo"].items()}
    merged_before.update({f"live:{k}": v for k, v in before["live"].items()})
    merged_after = {f"repo:{k}": v for k, v in after["repo"].items()}
    merged_after.update({f"live:{k}": v for k, v in after["live"].items()})
    return no_write_report(repo_root, live_root, merged_before, merged_after)
