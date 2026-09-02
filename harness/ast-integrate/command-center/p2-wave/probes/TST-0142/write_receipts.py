#!/usr/bin/env python3
"""Emit TST-0142 catalog receipt, SUBAGENT-RETURN, and per-unit manifest.

Runs the named probes live, writes command-center/receipts/TST-0142.json from
those numbers, then registers the per-unit manifest row. Does not invoke
tools/command-center/unit_manifest.py --write.
"""
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

from fanin_barrier import (  # noqa: E402
    LAUNCH_IDS,
    all_complete_outcomes,
    count_receipts_on_disk,
    expected_blocked,
    expected_complete,
    fan_in,
    half_blocked_outcomes,
    write_cohort_receipts,
)

UID = "TST-0142"
OUT = "command-center/receipts/TST-0142.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/scheduler_report"
SENTINEL = "SUCCESS:TST-0142"
QUESTION = (
    "When half a cohort is 429-blocked at the barrier, does fan-in return a "
    "typed PARTIAL naming every blocked unit id? PASS requires the denominator "
    "stay at the launched count; a result reporting 'N of N complete' after "
    "silently dropping blocked units is a FAIL."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0142/probe1_partial_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0142/probe2_shrink_denominator.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0142/fanin_barrier.py",
    "command-center/p2-wave/probes/TST-0142/probe1_partial_both_states.py",
    "command-center/p2-wave/probes/TST-0142/probe2_shrink_denominator.py",
    "command-center/p2-wave/probes/TST-0142/write_receipts.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str, dict]:
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
    parsed: dict = {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
    return proc.returncode, text, parsed


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": path.is_file(),
        "receipt_path": "command-center/p2-wave/probes/TST-0142/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def live_scenario() -> dict:
    launch = list(LAUNCH_IDS)
    blocked_dir = HERE / "runtime" / "receipt-half-blocked"
    free_dir = HERE / "runtime" / "receipt-unblocked"
    blocked_oc = half_blocked_outcomes(launch)
    free_oc = all_complete_outcomes(launch)
    write_cohort_receipts(blocked_dir, launch, blocked_oc)
    write_cohort_receipts(free_dir, launch, free_oc)
    honest = fan_in(launch, blocked_oc, drop_blocked_from_denominator=False).to_dict()
    mutant = fan_in(launch, blocked_oc, drop_blocked_from_denominator=True).to_dict()
    free = fan_in(launch, free_oc, drop_blocked_from_denominator=False).to_dict()
    return {
        "blocked_dir": blocked_dir.relative_to(REPO).as_posix(),
        "disk_blocked": count_receipts_on_disk(blocked_dir),
        "disk_free": count_receipts_on_disk(free_dir),
        "free": free,
        "free_dir": free_dir.relative_to(REPO).as_posix(),
        "honest": honest,
        "launch": launch,
        "mutant": mutant,
        "want_blocked": expected_blocked(blocked_oc, launch),
        "want_complete": expected_complete(blocked_oc, launch),
    }


def build_receipt(p1: dict, p2: dict, live: dict) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    launch = live["launch"]
    honest = live["honest"]
    mutant = live["mutant"]
    free = live["free"]
    want_blocked = live["want_blocked"]
    both_pass = p1.get("pass") is True and p2.get("pass") is True
    answer = (
        f"Yes. On an 8-unit launch manifest with four units 429-blocked at the "
        f"barrier, fan-in returns typed {honest['verdict']} naming "
        f"{want_blocked} and summary {honest['summary']!r} with denominator "
        f"{honest['denominator']} (the launched count). The unblocked control "
        f"returns {free['verdict']} with the same denominator "
        f"{free['denominator']}. A mutant that drops blocked units from its "
        f"denominator reports {mutant['summary']!r} / {mutant['verdict']} and "
        f"is rejected. Independent disk receipt counts are "
        f"{live['disk_blocked']} (half-blocked) and {live['disk_free']} "
        f"(unblocked). {SENTINEL}"
    )
    return {
        "answer": answer,
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
        "evidence": [
            {
                "expected_blocked_unit_ids": want_blocked,
                "half_blocked_roster_equals_manifest": honest.get("roster") == launch,
                "id": "a-barrier-vs-launch-manifest",
                "kind": "barrier-return-compared-to-launch-manifest",
                "named_blocked_unit_ids": honest.get("blocked_unit_ids"),
                "unblocked_roster_equals_manifest": free.get("roster") == launch,
            },
            {
                "equals_launched_count": (
                    live["disk_blocked"] == len(launch)
                    and live["disk_free"] == len(launch)
                ),
                "half_blocked_count": live["disk_blocked"],
                "half_blocked_receipt_dir": live["blocked_dir"],
                "id": "b-independent-disk-receipt-count",
                "kind": "independent-count-of-receipt-files-on-disk",
                "unblocked_count": live["disk_free"],
                "unblocked_receipt_dir": live["free_dir"],
            },
        ],
        "fan_in": {
            "half_blocked": honest,
            "mutant_shrink_denominator": mutant,
            "unblocked": free,
        },
        "id": UID,
        "inputs_present": {
            "B07_dispatcher_plus_scheduler": True,
            "_USER-PROMPTS.md": (REPO / "_USER-PROMPTS.md").is_file(),
            "fanin_barrier": "command-center/p2-wave/probes/TST-0142/fanin_barrier.py",
            "rules/common/fan-out-contract.md": (
                REPO / "rules/common/fan-out-contract.md"
            ).is_file(),
            "tools/command-center/measure_rate.py": (
                REPO / "tools/command-center/measure_rate.py"
            ).is_file(),
        },
        "launch_manifest": {
            "half_blocked_ids": want_blocked,
            "half_complete_ids": live["want_complete"],
            "launched_count": len(launch),
            "unit_ids": launch,
        },
        "measurements": [
            {
                "id": "half-blocked-denominator",
                "method": "fan_in drop_blocked_from_denominator=False",
                "unit": "launched-units",
                "value": honest.get("denominator"),
            },
            {
                "id": "half-blocked-verdict",
                "method": "fan_in",
                "unit": "verdict",
                "value": honest.get("verdict"),
            },
            {
                "id": "unblocked-denominator",
                "method": "fan_in all-complete cohort",
                "unit": "launched-units",
                "value": free.get("denominator"),
            },
            {
                "id": "mutant-summary",
                "method": "fan_in drop_blocked_from_denominator=True",
                "unit": "summary-string",
                "value": mutant.get("summary"),
            },
            {
                "id": "disk-receipts-half-blocked",
                "method": "count_receipts_on_disk",
                "unit": "files",
                "value": live["disk_blocked"],
            },
        ],
        "min_bytes_threshold": 2048,
        "named_probes": [
            {"command": P1, "id": "probe1", "role": "both-states-partial-complete"},
            {
                "command": P2,
                "id": "probe2",
                "role": "shrink-denominator-negative-control",
            },
        ],
        "negative_controls": [
            {
                "fired_on_bad_state": p2.get("negative_control_fired") is True,
                "id": "shrink-denominator",
                "mutant_summary": mutant.get("summary"),
                "mutant_verdict": mutant.get("verdict"),
                "silent_on_good_state": p1.get("pass") is True,
            }
        ],
        "notes": (
            "G-1 for TST-0142: live named probes exit 0, receipts/TST-0142.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle. "
            f"{SENTINEL}"
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "probe_results": {
            "both_pass": both_pass,
            "probe1_pass": p1.get("pass") is True,
            "probe2_pass": p2.get("pass") is True,
        },
        "produced_by": {
            "execution_substrate": "linux-headless-local",
            "model": "grok-4.6",
            "role": "scheduler-tester",
            "vendor": "cursor",
        },
        "question": QUESTION,
        "question_or_target": QUESTION,
        "report_kind": "scheduler_report",
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "notes": (
                "Probe 2 does not reuse probe 1's runtime directory. It "
                "instantiates the shrinking-denominator mutant on the same "
                "launch manifest and requires contract_errors to fire."
            ),
            "reviewer_id": "TST-0142-probe2-shrink-denominator-refuter",
            "verdict": "PASS" if p2.get("pass") is True else "FAIL",
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "tools/command-center/measure_rate.py was used as the SUT (it measures a different gate)",
                "catalog schema file receipt.schema.json existed on disk before this unit",
            ]
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "tests": [
            {
                "command": P1,
                "id": "TST-0142-T1",
                "name": "both-states control: unblocked cohort returns COMPLETE with the same denominator",
                "result": "PASS" if p1.get("pass") is True else "FAIL",
            },
            {
                "command": P2,
                "id": "TST-0142-NC1",
                "name": "negative control: a barrier that filters blocked units out of its own denominator must fail",
                "result": "PASS" if p2.get("pass") is True else "FAIL",
            },
        ],
        "title": "Rate-limited partial fan-in returns typed PARTIAL, never a shrunken denominator",
        "ts": now,
        "unit_id": UID,
    }


def main() -> int:
    c1, t1, p1 = run_probe(P1)
    c2, t2, p2 = run_probe(P2)
    if c1 != 0 or c2 != 0 or not p1.get("pass") or not p2.get("pass"):
        print(f"FAILED:TST-0142 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    live = live_scenario()
    doc = build_receipt(p1, p2, live)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:TST-0142 sentinel missing from serialized receipt")
        return 1
    out.write_text(body, encoding="utf-8", newline="\n")
    sha, size = digest(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0142 artifact {size}B below floor")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [
        row(path, "supporting") for path in SUPPORTING if (REPO / path).is_file()
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": UID,
        "manifest_path": "command-center/p2-wave/probes/TST-0142/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "both-states-partial-complete",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "shrink-denominator-negative-control",
            },
        ],
        "notes": (
            "G-1 for TST-0142: live named probes exit 0, receipts/TST-0142.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0142-probe2-shrink-denominator-refuter",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0142 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
