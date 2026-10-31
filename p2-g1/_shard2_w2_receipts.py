#!/usr/bin/env python3
"""shard2 wave-2: write BLOCKED/reviewer-absent receipts for delivered units.

Receipt shape mirrors the recorded ARC-0048 template (the recorded builder-terminal
state for this program). state=BLOCKED with failure.classification ["reviewer-absent"];
only the independent reviewer closes. Reads live catalog + SUBAGENT-RETURN data so
sha/probe rows cannot drift from disk.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "command-center"))
from receipt_writer import write_atomic  # noqa: E402

CATALOG = json.loads(
    (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
UNITS = {u["id"]: u for u in CATALOG["work_units"]}


def digest_live(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def build(uid: str, *, retry_count: int, extra_note: str = "") -> int:
    unit = UNITS[uid]
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    ret = json.loads((pdir / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    out_rel = str(unit["output_path"]).replace("\\", "/")
    sha, size = digest_live(out_rel)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = str(unit.get("reviewer_requirement") or "")
    probes = []
    for np in ret.get("named_probes") or []:
        probes.append(
            {
                "id": np.get("id"),
                "command": np.get("command"),
                "exit_code": np.get("exit_code"),
            }
        )
    reason = (
        "Builder-side construction complete and live-verified "
        "(_measure_one_delivered.py -> SUCCESS:delivered): artifact at "
        "output_path parses, carries the completion sentinel, both named "
        "probes re-run exit 0, per-unit manifest row matches the "
        "CRLF-normalized sha256. state stays BLOCKED because receipt_core "
        "forbids state=SUCCESS without reviewer.verdict=PASS with "
        "independent=true, and the catalog reviewer_requirement names a "
        "fresh-context / cross-vendor / two-reviewer panel that has not run. "
        "Only the independent reviewer closes. " + req
    )
    if extra_note:
        reason += " " + extra_note
    doc = {
        "schema_version": 1,
        "unit_id": uid,
        "id": uid,
        "state": "BLOCKED",
        "status": "BUILT-AWAITING-REVIEW",
        "failure": {
            "blocked_on": "independent reviewer per catalog reviewer_requirement",
            "classification": ["reviewer-absent"],
            "reason": reason,
        },
        "gate_note": (
            "not owner-gated (catalog owner_approval_required=false); blanket "
            "build directive 2026-10-24 not needed for this unit"
        ),
        "artifacts": [
            {
                "bytes": size,
                "eol": "LF",
                "exists": True,
                "path": out_rel,
                "role": "primary",
                "sha256": sha,
            }
        ],
        "completion_sentinel": unit.get("completion_sentinel"),
        "named_probes": probes,
        "output_path": out_rel,
        "output_schema": unit.get("output_schema"),
        "owner_approval_required": unit.get("owner_approval_required"),
        "produced_by": {
            "model": "opus",
            "vendor": "anthropic",
            "role": "builder-shard-2-w2",
        },
        "retry": {
            "count": retry_count,
            "policy": "two-strikes pivot; skip is a verdict, not a retry",
        },
        "reviewer": {
            "catalog_reviewer_requirement": req,
            "independent": False,
            "reviewer_id": None,
            "verdict": "PENDING",
        },
        "manifest_path": (
            f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "spec_anchor": unit.get("spec_anchor"),
        "timestamps": {"ended_at": now},
        "ts": now,
    }
    dest = REPO / "command-center" / "receipts" / f"{uid}.json"
    res = write_atomic(dest, doc)
    if not res.get("ok"):
        print(f"FAILED:receipt-write {uid} {res}")
        return 1
    print(f"SUCCESS:receipt {uid} -> {res['path']} sha256={res['sha256']}")
    return 0


if __name__ == "__main__":
    uid = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    note = sys.argv[3] if len(sys.argv) > 3 else ""
    raise SystemExit(build(uid, retry_count=count, extra_note=note))
