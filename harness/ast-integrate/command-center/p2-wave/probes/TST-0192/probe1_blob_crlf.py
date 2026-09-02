#!/usr/bin/env python3
"""Probe 1: CR byte counts over blobs/worktree + *.sh eol=lf (signal a).

Mechanically different from probe 2: does not run the Git-Bash analogue or the
CRLF both-states plant. Re-counts CR bytes and re-parses .gitattributes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from detectors import (  # noqa: E402
    blob_or_worktree_cr,
    gitattributes_status,
    inventory_sh,
    parse_sh_eol_lf,
    receipt_shell_fields,
)
from emitter import emit  # noqa: E402

ART = REPO / "command-center/receipts/TST-0192.json"
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:TST-0192-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0192" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")
    fields = receipt_shell_fields(doc)
    if fields["kind"] != "shell_report":
        return fail("report_kind")

    emit()
    ga = gitattributes_status()
    if not ga.get("has_sh_eol_lf"):
        return fail("live .gitattributes lacks *.sh eol=lf")
    rec_ga = fields["gitattributes"]
    if rec_ga.get("has_sh_eol_lf") is not True:
        return fail("receipt gitattributes.has_sh_eol_lf is not true")

    mutant = parse_sh_eol_lf("*.py text eol=lf\n")
    if mutant["has_sh_eol_lf"]:
        return fail("gitattributes parser is vacuous (fires without *.sh)")

    rec_scripts = {
        r["path"]: r for r in fields["emitted_scripts"] if isinstance(r, dict)
    }
    live = []
    for path in inventory_sh():
        rel = path.relative_to(REPO).as_posix()
        cr = blob_or_worktree_cr(path, rel)
        live.append({"path": rel, **cr})
        if cr["cr_count_live"] != 0:
            return fail(f"{rel} cr_count={cr['cr_count_live']} source={cr['live_source']}")
        claimed = rec_scripts.get(rel)
        if claimed is None:
            return fail(f"{rel} missing from receipt emitted_scripts")
        if claimed.get("cr_count") != 0:
            return fail(f"receipt cr_count for {rel} is {claimed.get('cr_count')}")
        if cr.get("used_git_archive"):
            return fail("git archive used")

    if len(live) < 2:
        return fail("inventory too small")

    out = {
        "probe": "probe1-blob-crlf",
        "unit_id": "TST-0192",
        "gitattributes": ga,
        "scripts": [
            {
                "path": r["path"],
                "cr_count_live": r["cr_count_live"],
                "live_source": r["live_source"],
                "blob_ok": (r.get("blob") or {}).get("ok"),
            }
            for r in live
        ],
        "used_git_archive": False,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0192-probe1 blob CR counts and gitattributes eol=lf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
