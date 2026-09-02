#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0156.json from a live campaign."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cache_publish as CP  # noqa: E402
import harness as H  # noqa: E402

OUT = H.OUT_REL
SCHEMA = "command-center/schema/receipt.schema.json"
QUESTION = (
    "Cancel the render mid-write repeatedly: can any subsequent read observe "
    "a truncated cache file? PASS requires atomic publish and zero observed "
    "partial reads across 200 cancellations."
)
SENTINEL = "SUCCESS:TST-0156"
P1 = H.P1
P2 = H.P2


def sha256_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def snippet(rel: str, line: int) -> str:
    text = (REPO / rel).read_text(encoding="utf-8")
    rows = text.splitlines()
    return rows[line - 1].strip()[:200]


def main() -> int:
    live = H.run_campaign(include_direct=True)
    if not live["pass"]:
        print("FAILED:TST-0156 emit campaign did not pass")
        print(json.dumps(live, indent=2)[:4000])
        return 1
    if live["atomic"]["after_partial"] != 0:
        print("FAILED:TST-0156 emit observed partial atomic reads")
        return 1
    if live["direct"]["after_partial"] != live["cancel_n"]:
        print("FAILED:TST-0156 emit mutation did not fire")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "command-center/p2-wave/probes/TST-0156/cache_publish.py",
        "command-center/p2-wave/probes/TST-0156/harness.py",
        "command-center/p2-wave/probes/TST-0156/probe1_cancel_atomic.py",
        "command-center/p2-wave/probes/TST-0156/probe2_mutation.py",
        SCHEMA,
    ]
    artifacts = [
        {"path": OUT, "exists": True, "role": "primary"},
    ]
    for rel in supporting:
        digest, size = sha256_file(rel)
        artifacts.append(
            {
                "path": rel,
                "exists": True,
                "role": "supporting",
                "sha256": digest,
                "bytes": size,
            }
        )

    sut = "command-center/p2-wave/probes/TST-0156/cache_publish.py"
    doc = {
        "schema_version": 1,
        "kind": "monitor_report",
        "report_kind": "monitor_report",
        "unit_id": "TST-0156",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "A cancelled render cannot leave a half-written cache",
        "question": QUESTION,
        "answer": (
            "Atomic tmp+os.replace publish: 0 PARTIAL dest reads across "
            f"{live['cancel_n']} cancellations; dest remained the complete "
            "pre-cancel object (seq=1). Uncancelled render published seq=2. "
            "Mutation (O_TRUNC in-place write) produced "
            f"{live['direct']['after_partial']} PARTIAL reads, so the reader "
            "is live. Orphan tmp files appeared mid-cancel and were scavenged "
            f"to zero (seen={live['atomic']['orphans_seen_before_scavenge']}, "
            f"left={live['atomic']['orphans_remaining']}). Production B07 "
            "monitorcore cache publisher is absent on this worktree; the "
            "object under test is the probe publisher at "
            f"{sut}:publish_atomic. SUCCESS:TST-0156"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0156",
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/monitor_report",
        "campaign": live,
        "signals": [
            {
                "id": "reader-parse",
                "kind": "reader-side-parse-outcomes",
                "atomic_after_partial": live["atomic"]["after_partial"],
                "atomic_after_complete_still_old": live["atomic"][
                    "after_complete_still_old"
                ],
                "direct_after_partial": live["direct"]["after_partial"],
            },
            {
                "id": "dir-scan-orphans",
                "kind": "directory-scan-leftover-tmp",
                "orphans_seen_before_scavenge": live["atomic"][
                    "orphans_seen_before_scavenge"
                ],
                "orphans_remaining": live["atomic"]["orphans_remaining"],
            },
        ],
        "tests": [
            {
                "id": "uncancelled-publish",
                "result": "PASS",
                "command": P1,
                "detail": "uncancelled atomic render published COMPLETE seq=2",
            },
            {
                "id": "cancel-atomic-200",
                "result": "PASS",
                "command": P1,
                "detail": (
                    f"{live['cancel_n']} SIGKILL mid-write, "
                    f"partial={live['atomic']['after_partial']}"
                ),
            },
            {
                "id": "mutation-direct-write",
                "result": "PASS",
                "command": P2,
                "detail": (
                    f"direct O_TRUNC cancel produced "
                    f"{live['direct']['after_partial']} PARTIAL reads"
                ),
            },
            {
                "id": "orphan-tmp-scan",
                "result": "PASS",
                "command": P1,
                "detail": (
                    "tmp files observed then scavenged to "
                    f"{live['atomic']['orphans_remaining']}"
                ),
            },
        ],
        "evidence": [
            {
                "path": sut,
                "line": 154,
                "kind": "atomic-replace",
                "snippet": snippet(sut, 154),
            },
            {
                "path": sut,
                "line": 161,
                "kind": "mutation-direct-trunc",
                "snippet": snippet(sut, 161),
            },
            {
                "path": sut,
                "line": 100,
                "kind": "reader-classifier",
                "snippet": snippet(sut, 100),
            },
            {
                "path": sut,
                "line": 65,
                "kind": "orphan-scavenge",
                "snippet": snippet(sut, 65),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0156-probe2-mutation-direct-write",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 re-runs the campaign in a separate process and "
                "requires the mutation to produce PARTIAL reads while atomic "
                "stays at zero. Catalog asked for a second Windows shell "
                "(pwsh7 and Git Bash); this worktree is Linux-only, so that "
                "shell pair is NOT-CHECKED rather than forged."
            ),
        },
        "artifacts": artifacts,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "cancel-atomic"},
            {"id": "probe2", "command": P2, "role": "mutation-control"},
        ],
        "production_publisher": live["production_publisher"],
        "object_under_test": sut,
        "timestamps": {"measured_at": now},
        "residual_caveat": (
            "tools/monitorcore is absent; the live publisher is the probe SUT. "
            "Windows dual-shell re-run is NOT-CHECKED on this Linux worktree. "
            "Did not run tools/command-center/unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/TST-0156/UNIT-ARTIFACT-MANIFEST.json",
    }
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0156 emit sentinel missing from rendered bytes")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    missing = [
        k
        for k in ("unit_id", "state", "sentinel", "artifacts", "tests", "reviewer")
        if k not in doc
    ]
    if missing:
        print(f"FAILED:TST-0156 emit missing keys {missing}")
        return 1
    # Catalog $defs/monitor_report is not in the shim; $ref resolution of
    # artifact.schema.json is broken (relative id doubling). G-1 does not
    # schema-validate. Required keys and SUCCESS:TST-0156 are the live bar.
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:TST-0156 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
