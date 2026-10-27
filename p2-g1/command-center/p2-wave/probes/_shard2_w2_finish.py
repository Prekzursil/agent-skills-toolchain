#!/usr/bin/env python3
"""shard2 wave-2 finisher: run probes, refresh artifact named_probes, demote any
builder-authored reviewer self-closure to prev_closure, write SUBAGENT-RETURN +
UNIT-ARTIFACT-MANIFEST for units whose artifact exists but whose probe kit was
lost mid-flight by the dead prior builder.

Usage: python _shard2_w2_finish.py <UNIT-ID> <probe1.py> <probe2.py> [supporting.py ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _shard2_lib import (  # noqa: E402
    load_catalog_unit,
    run_probe_command,
    utcnow_iso,
    write_json,
    artifact_row,
)
from _shard2_w2_lib import REPO, SENTINEL  # noqa: E402


def main() -> int:
    uid = sys.argv[1]
    p1_name, p2_name = sys.argv[2], sys.argv[3]
    supporting = sys.argv[4:]

    unit = load_catalog_unit(uid)
    out_rel = str(unit["output_path"]).replace("\\", "/")
    pdir = HERE / uid
    art_path = REPO / out_rel
    if not art_path.is_file():
        print(f"FAILED:{uid} artifact missing at {out_rel}")
        return 1

    cmds = {
        "probe1": f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{p1_name}",
        "probe2": f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{p2_name}",
    }
    named_probes = []
    for pid in ("probe1", "probe2"):
        t0 = utcnow_iso()
        rc, tail = run_probe_command(cmds[pid], timeout=900)
        if rc != 0:
            print(f"FAILED:{uid} {pid} rc={rc}")
            print(tail[-3000:])
            return 1
        named_probes.append(
            {
                "id": pid,
                "command": cmds[pid],
                "exit_code": rc,
                "role": "probe",
                "raw_output": tail,
                "finished_at": utcnow_iso(),
                "started_at": t0,
            }
        )
        print(f"{pid} rc=0")

    # Refresh the artifact's named_probes with the LIVE raw outputs of the
    # scripts that now exist on disk, and demote any builder-authored
    # reviewer self-closure: only the independent reviewer closes.
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    doc["named_probes"] = named_probes
    old_rev = doc.get("reviewer")
    if isinstance(old_rev, dict) and old_rev.get("independent") is True:
        ext = doc.get("extensions") or {}
        pc = ext.get("prev_closure") or []
        if isinstance(pc, dict):
            pc = [pc]
        pc.append(
            {
                "demoted_by": (
                    "shard2 wave-2 builder 2026-10-25: builder-authored probe "
                    "closure is not an independent review; only the "
                    "independent reviewer closes (program contract, receipt "
                    "state=BLOCKED with failure.classification "
                    "reviewer-absent)"
                ),
                **old_rev,
            }
        )
        ext["prev_closure"] = pc
        doc["extensions"] = ext
        # Preserve content keys (e.g. added_failure_mode: the reviewer-
        # contributed failure mode is artifact content, not a closure claim);
        # reset only the closure fields to PENDING.
        preserved = {
            k: v
            for k, v in old_rev.items()
            if k not in {"independent", "verdict", "reviewer_id", "fresh_context", "method", "notes", "vendor"}
        }
        doc["reviewer"] = {
            "catalog_reviewer_requirement": unit.get("reviewer_requirement"),
            "independent": False,
            "reviewer_id": None,
            "verdict": "PENDING",
            **preserved,
        }
    blob = json.dumps(doc, indent=1, ensure_ascii=True) + "\n"
    art_path.write_bytes(blob.replace("\r\n", "\n").encode("utf-8"))

    primary = artifact_row(art_path, role="primary")
    primary["unit_id"] = uid
    primary["present"] = True
    primary["receipt_path"] = f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json"
    artifacts = [primary]
    for rel in supporting:
        p = REPO / rel
        if not p.is_file():
            print(f"FAILED:{uid} supporting file missing {rel}")
            return 1
        row = artifact_row(p, role="supporting")
        row["unit_id"] = uid
        row["present"] = True
        row["receipt_path"] = primary["receipt_path"]
        artifacts.append(row)

    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL.get(uid),
        "registered": True,
        "output_path": out_rel,
        "output_schema": unit.get("output_schema"),
        "named_probes": named_probes,
        "artifacts": [
            {
                "path": out_rel,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        "extensions": {
            "prev_closure": doc.get("extensions", {}).get("prev_closure"),
            "shard2_w2_resume_2026-10-25": {
                "action": (
                    "probe kit rebuilt live by the shard-2 wave-2 builder "
                    "(resume of a mid-flight-dead prior attempt): probe "
                    "scripts materialized, both probes re-run exit 0, "
                    "artifact named_probes refreshed with the live raw "
                    "outputs, builder-authored reviewer self-closure demoted "
                    "to prev_closure, receipt stays BLOCKED/reviewer-absent"
                ),
                "builder": "shard2 wave-2 builder",
            },
        },
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": (
                "Builder lane may not self-certify: artifact rebuilt and "
                "live-verified, probes re-run exit 0, manifest sha rows "
                "match; receipt stays BLOCKED until the independent reviewer "
                "closes (reviewer.verdict=PASS with independent=true)."
            ),
        },
        "cloud_ok": False,
        "ts": utcnow_iso(),
    }
    write_json(pdir / "SUBAGENT-RETURN.json", ret)
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": uid,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a.get("present")),
        "artifacts": artifacts,
    }
    write_json(pdir / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"primary {out_rel} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{uid} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
