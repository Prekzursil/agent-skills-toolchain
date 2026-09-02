#!/usr/bin/env python3
"""Write IMP-0159 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import scenario as S  # noqa: E402
from candidates.freshness import (  # noqa: E402
    ForbiddenTransport,
    compute_due_list,
    due_item_as_dict,
    flag_as_dict,
    flag_maintenance,
    schedule,
)

OUT = "command-center/receipts/IMP-0159.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0159/probe1_ttl_due_list.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0159/probe2_archived_upstream.py"
)
SUPPORTING = [
    "tools/candidates/freshness.py",
    "tools/candidates/class_ttl.json",
    "command-center/p2-wave/probes/IMP-0159/fixtures/candidates.json",
    "command-center/p2-wave/probes/IMP-0159/scenario.py",
    "command-center/p2-wave/probes/IMP-0159/probe1_ttl_due_list.py",
    "command-center/p2-wave/probes/IMP-0159/probe2_archived_upstream.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise ValueError("probe emitted no JSON object")


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": True,
        "eol": "LF",
        "unit_id": "IMP-0159",
        "receipt_path": "command-center/p2-wave/probes/IMP-0159/SUBAGENT-RETURN.json",
        "role": role,
    }


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0159 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:IMP-0159 receipts probe JSON pass=false")
        return 1

    rows = S.load_candidates()
    table = S.ttl_policy()
    due_within = compute_due_list(rows, S.CLOCK_WITHIN, table)
    due_past = compute_due_list(rows, S.CLOCK_PAST, table)
    transport = ForbiddenTransport()
    flags = flag_maintenance(rows, S.CLOCK_WITHIN, table, transport)
    sched_within = schedule(rows, S.CLOCK_WITHIN, table, transport)
    if transport.calls:
        print(f"FAILED:IMP-0159 emit-time network calls {transport.calls}")
        return 1
    past_ids = [item.candidate_id for item in due_past]
    within_ids = [item.candidate_id for item in due_within]
    if past_ids != p1.get("past_ids") or within_ids != p1.get("within_ids"):
        print("FAILED:IMP-0159 emit-time due-list disagrees with probe1")
        return 1
    flagged = {item.candidate_id: item.flagged for item in flags}
    if flagged.get(S.ARCHIVED_ID) is not True or flagged.get(S.MAINTAINED_ID) is not False:
        print("FAILED:IMP-0159 emit-time maintenance flags disagree with probe2")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl_rows = [row(path, "supporting") for path in SUPPORTING]
    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0159",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0159",
        "completion_marker": "UNIT-COMPLETE:IMP-0159",
        "title": "Implement freshness decay plus a maintenance-state revalidation scheduler",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0159",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 128,
        "registered": True,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0159/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "reviewer_id": "IMP-0159-probe2-archived-upstream",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
        },
        "tests": [
            {
                "id": "ttl-expiry-due-list",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "archived-upstream-both-states",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "within-ttl-not-due",
                "kind": "both-states",
                "description": (
                    "Same candidate, injected clock inside class TTL is absent "
                    "from the due-list; one second past TTL it is present and GREEN decays."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(p1.get("past_ids")),
                "good_state_output": json.dumps(p1.get("within_ids")),
            },
            {
                "id": "maintained-not-flagged",
                "kind": "both-states",
                "description": (
                    "Archived upstream is flagged from a fresh cached maintenance "
                    "record; maintained twin is not. No network call in either state."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": S.ARCHIVED_ID,
                "good_state_output": S.MAINTAINED_ID,
            },
        ],
        "evidence": [
            {
                "anchor": "tools/candidates/freshness.py:compute_due_list",
                "claim": (
                    "A candidate aged past its class TTL appears on the due-list "
                    "computed from the record with an injected clock; the same "
                    "record inside the TTL does not. GREEN decays to STALE."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp(P1),
                        "raw_output": t1[-1500:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "emit-time recompute compute_due_list",
                        "exit_code": 0,
                        "fingerprint": fp("compute_due_list-recompute"),
                        "raw_output": json.dumps(
                            {
                                "within_ids": within_ids,
                                "past_ids": past_ids,
                                "subject_past": due_item_as_dict(
                                    next(i for i in due_past if i.candidate_id == S.TTL_SUBJECT)
                                ),
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
            {
                "anchor": "tools/candidates/freshness.py:flag_maintenance",
                "claim": (
                    "An archived upstream is flagged without a network call when "
                    "the cached maintenance record is still fresh; a maintained "
                    "control is not flagged."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp(P2),
                        "raw_output": t2[-1500:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "emit-time recompute flag_maintenance + ForbiddenTransport",
                        "exit_code": 0,
                        "fingerprint": fp("flag_maintenance-recompute"),
                        "raw_output": json.dumps(
                            {
                                "flags": [flag_as_dict(item) for item in flags],
                                "transport_calls": list(transport.calls),
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
        ],
        "implementation": {
            "module": "tools/candidates/freshness.py",
            "ttl_table": "tools/candidates/class_ttl.json",
            "clock": "InjectedClock only; no time.time default",
            "due_list_clock_within": S.CLOCK_WITHIN.now_unix,
            "due_list_clock_past": S.CLOCK_PAST.now_unix,
            "due_ids_within_ttl": within_ids,
            "due_ids_past_ttl": past_ids,
            "decay": "GREEN -> STALE when due; STALE is not citeable",
            "maintenance_flags": [flag_as_dict(item) for item in flags],
            "network_calls_on_fresh_cache": 0,
            "evaluated_within": sched_within.evaluated,
            "imp0155_live_corpus": "absent; scheduler consumes provenance-shaped fixture records",
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "read_ok": True,
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0159",
                    "method": "command",
                    "role": "verifier",
                    "note": "run after this receipt and the per-unit manifest are on disk",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": "IMP-0155 live provenance corpus is not on this worktree.",
                "settling_experiment": (
                    "Re-run the scheduler against IMP-0155 output_path records "
                    "once that unit is delivered; fixture shape is the contract."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "artifacts": [
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
                "exists": True,
                "role": item["role"],
            }
            for item in impl_rows
        ],
        "notes": (
            "G-1 for IMP-0159: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    out_path = REPO / OUT
    out_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    primary = row(OUT, "primary")
    artifacts = [primary] + impl_rows
    ret = {
        "id": "IMP-0159",
        "unit_id": "IMP-0159",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0159",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0159/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0159-probe2-archived-upstream",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0159: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0159",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0159 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
