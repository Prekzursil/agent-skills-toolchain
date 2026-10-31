#!/usr/bin/env python3
"""Shard21 w3: additive report blocks for the TST-0161 receipt.

The receipt predates the per-probe anchor shape; the probes (authored later
by the dead prior shard) verify report.conflict / report.independent /
report.expiry_enforced against live runs. The live Windows runs of the probe
scenarios measure exactly those blocks; record them with provenance.
State and reviewer closure are left untouched.
"""
import json
import sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0161"
sys.path.insert(0, str(HERE))
from scenarios import concurrent_conflict, expiry_mid_write, overlapping_conflict  # noqa: E402

p = REPO / "command-center" / "receipts" / "TST-0161.json"
doc = json.loads(p.read_text(encoding="utf-8"))

import tempfile

with tempfile.TemporaryDirectory(prefix="tst-0161-receipt-") as td:
    root = Path(td)
    conflict = overlapping_conflict(root / "cf")
    concurrent = concurrent_conflict(root / "cc")
    enforced = expiry_mid_write(root / "en", write_time_recheck=True)

if not conflict.get("ok") or not concurrent.get("ok") or not enforced.get("ok"):
    print("FAILED:update-0161 live scenarios did not pass")
    print(json.dumps({
        "conflict_ok": conflict.get("ok"),
        "concurrent_ok": concurrent.get("ok"),
        "enforced_ok": enforced.get("ok"),
    }))
    raise SystemExit(1)

report = doc.setdefault("report", {})
if "conflict" not in report:
    second = conflict.get("second_conflict") or {}
    report["conflict"] = {
        "second_conflict": {
            "kind": second.get("kind"),
            "ok": second.get("ok"),
            "reason": second.get("reason"),
            "holder": second.get("holder"),
            "requester": second.get("requester"),
            "holder_fence": second.get("holder_fence"),
        },
        "double_grants": concurrent.get("double_grants"),
        "silent_or_untyped": concurrent.get("silent_or_untyped"),
        "trials": concurrent.get("trials"),
    }
    report["independent"] = {
        "both_granted": bool(conflict.get("first_grant", {}).get("ok"))
        and bool(conflict.get("holder_renew", {}).get("ok"))
        and second.get("ok") is False
    }
    commit_a = enforced.get("commit_a") or {}
    report["expiry_enforced"] = {
        "commit_a": {
            "ok": commit_a.get("ok"),
            "kind": commit_a.get("kind"),
            "reason": commit_a.get("reason"),
            "presented_fence": commit_a.get("presented_fence"),
            "current_fence": commit_a.get("current_fence"),
        },
        "published_is_transferee": enforced.get("published_is_transferee"),
    }
    report["windows_revalidation"] = {
        "date": "2026-10-26",
        "builder": "shard21-wave3 (builder, not reviewer)",
        "change": (
            "lease.py _PathLock ported from fcntl.flock to msvcrt.locking "
            "one-byte range lock with bounded retry; flock branch preserved "
            "verbatim for POSIX. report.conflict / report.independent / "
            "report.expiry_enforced recorded from live re-runs of the probe "
            "scenarios on Windows (overlapping_conflict, "
            "concurrent_conflict x16, expiry_mid_write recheck=True)."
        ),
    }
p.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("receipt updated: report blocks added")
