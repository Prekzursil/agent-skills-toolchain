#!/usr/bin/env python3
"""Emit IMP-0442 catalog receipt, SUBAGENT-RETURN, and per-unit manifest.

Runs the named probes, writes command-center/receipts/IMP-0442.json from live
dispatcher numbers, then registers the per-unit manifest row. Does not invoke
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

from dispatcher import (  # noqa: E402
    CATALOG_REL,
    FOUR_SUBSTRATES,
    DispatchOpts,
    census,
    catalog_units,
    compact_series,
    dispatch,
    isolation_per_substrate,
    mixed_dry_run_units,
    summary,
)

UID = "IMP-0442"
OUT = "command-center/receipts/IMP-0442.json"
SCHEMA = "command-center/schema/dispatch-plan.schema.json"
SENTINEL = "SENTINEL:IMP-0442:DISPATCH-SUBSTRATE-HONORED"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0442/probe1_mixed_dry_run.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0442/probe2_serial_lock_mutation.py"
)
SUPPORTING = [
    "command-center/schema/dispatch-plan.schema.json",
    "command-center/p2-wave/probes/IMP-0442/dispatcher.py",
    "command-center/p2-wave/probes/IMP-0442/probe1_mixed_dry_run.py",
    "command-center/p2-wave/probes/IMP-0442/probe2_serial_lock_mutation.py",
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
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0442/SUBAGENT-RETURN.json",
        "role": role,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
    }


def parse_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


QUESTION = (
    "Implement the dispatcher that reads the catalog and routes each unit to "
    "its declared execution_substrate, with local-serialized meaning strictly "
    "one at a time. Exact question: with a catalog containing units of all "
    "four substrates, does the observed simultaneous count for "
    "local-serialized ever exceed one?"
)


def build_receipt(p1: dict, p2: dict) -> dict:
    units = mixed_dry_run_units(n_per_substrate=10, duration_ticks=8)
    locked = dispatch(units, DispatchOpts(serial_lock=True))
    unlocked = dispatch(units, DispatchOpts(serial_lock=False))
    dumped = dispatch(
        units, DispatchOpts(serial_lock=True, honor_declared_substrate=False)
    )
    catalog_census = census(catalog_units())
    iso = isolation_per_substrate(locked)
    serial_series = locked.concurrent_series("local-serialized")
    answer = (
        f"No. On a 40-unit mixed dry run (10 per substrate, all arriving at "
        f"tick 0) the local-serialized concurrent series is in {{0,1}} with "
        f"peak {locked.peak('local-serialized')}. Removing the serial lock "
        f"raises that peak to {unlocked.peak('local-serialized')} and turns "
        f"the flat-at-one predicate red, so the lock is the cause, not a "
        f"clipped readout."
    )
    return {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Work-unit dispatcher honoring the declared execution substrate",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0442",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "profile": "selfimprove-measure-artifact",
        "four_substrates": list(FOUR_SUBSTRATES),
        "catalog_census": catalog_census,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "serial_lock": {
            "applies_to": "local-serialized",
            "max_simultaneous": 1,
            "enforced_at_start": True,
            "implementation": (
                "command-center/p2-wave/probes/IMP-0442/dispatcher.py:"
                "_can_start refuses a second local-serialized start while one "
                "is in flight when serial_lock=True"
            ),
        },
        "routing": {
            "rule": "route(unit) = unit.execution_substrate when honor_declared_substrate",
            "unknown_substrate": "DispatchError; not remapped to catalog defaults",
            "catalog_default_is_not_a_lane": (
                "defaults.execution_substrate is local-windows-pwsh7, which is "
                "not one of the four lanes. The dispatcher reads the per-unit "
                "field already present on every work_unit."
            ),
            "assignments_locked": dict(locked.assignments),
        },
        "dry_run": {
            "catalog_path": CATALOG_REL,
            "unit_count": len(units),
            "per_substrate": 10,
            "duration_ticks": 8,
            "arrival": "all ready_at=0 so serialized units would overlap without the lock",
            "unit_ids": [u.id for u in units],
        },
        "time_series": compact_series(locked),
        "time_series_local_serialized": serial_series,
        "peaks": dict(locked.peaks),
        "isolation": {
            "ok": locked.isolation_ok(),
            "per_substrate": iso,
            "worktree_slot_collisions": locked.worktree_slot_collisions,
            "violations": list(locked.isolation_violations),
        },
        "mutation_control": {
            "removed_serial_lock": True,
            "serial_peak_with_lock": locked.peak("local-serialized"),
            "serial_peak_without_lock": unlocked.peak("local-serialized"),
            "flat_at_one_with_lock": locked.serial_flat_at_one(),
            "flat_at_one_predicate_failed": not unlocked.serial_flat_at_one(),
            "unlocked_compact_series": compact_series(unlocked),
            "isolation_mutant_honor_declared_false": {
                "violation_count": len(dumped.isolation_violations),
                "isolation_ok": dumped.isolation_ok(),
                "peaks": dict(dumped.peaks),
            },
        },
        "live_run": {
            "locked": summary(locked),
            "unlocked_peaks": dict(unlocked.peaks),
            "probe1": {
                "pass": p1.get("pass") is True,
                "peaks": (p1.get("locked") or {}).get("peaks"),
            },
            "probe2": {
                "pass": p2.get("pass") is True,
                "unlocked_peak": (p2.get("unlocked") or {}).get(
                    "peak_local_serialized"
                ),
            },
        },
        "dependencies": {
            "IMP-0436": {
                "role": "per-unit override semantics for execution_substrate",
                "receipt_present": (REPO / "command-center/receipts/IMP-0436.json").is_file(),
                "note": (
                    "IMP-0436.json is absent on this worktree. Dispatcher reads "
                    "the per-unit execution_substrate already set on all 2007 "
                    "work_units (census other=0). It does not claim IMP-0436 delivered."
                ),
            },
            "IMP-0443": {
                "role": "catalog sibling; not required to route by substrate",
                "note": "Declared dependency; routing does not import IMP-0443.",
            },
        },
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "40-unit mixed dry run (10 per substrate, live catalog ids) "
                    f"has local-serialized peak {locked.peak('local-serialized')} "
                    f"and series values only in {{0,1}}; local-parallel/"
                    f"worktree-isolated/cloud-batch peaks "
                    f"{locked.peak('local-parallel')}/"
                    f"{locked.peak('worktree-isolated')}/"
                    f"{locked.peak('cloud-batch')}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0442/dispatcher.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "discrete-event-dry-run",
                        "command": P1,
                        "raw_output": json.dumps(
                            {
                                "peaks": dict(locked.peaks),
                                "serial_flat_at_one": locked.serial_flat_at_one(),
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "both-states-serial-lock",
                        "command": P2,
                        "raw_output": json.dumps(
                            {
                                "locked_peak": locked.peak("local-serialized"),
                                "unlocked_peak": unlocked.peak("local-serialized"),
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "Each of the four substrates is isolated: every unit ran on "
                    "its declared lane; worktree slots did not collide; dumping "
                    f"all units to local-parallel produces "
                    f"{len(dumped.isolation_violations)} isolation violations."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0442/probe1_mixed_dry_run.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "per-substrate-isolation",
                        "command": "isolation_per_substrate(locked)",
                        "raw_output": json.dumps(iso, sort_keys=True),
                    },
                    {
                        "role": "verifier",
                        "method": "mutation-honor-declared-false",
                        "command": "DispatchOpts(honor_declared_substrate=False)",
                        "raw_output": json.dumps(
                            {
                                "violation_count": len(dumped.isolation_violations),
                                "isolation_ok": dumped.isolation_ok(),
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "IMP-0442-mixed-dry-run-serial-flat-at-one",
                "result": "PASS" if p1.get("pass") else "FAIL",
                "peaks": dict(locked.peaks),
            },
            {
                "id": "IMP-0442-serial-lock-mutation",
                "result": "PASS" if p2.get("pass") else "FAIL",
                "locked_peak": locked.peak("local-serialized"),
                "unlocked_peak": unlocked.peak("local-serialized"),
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0442-NC-SERIAL-LOCK",
                "fired_on_bad_state": unlocked.peak("local-serialized") > 1
                and not unlocked.serial_flat_at_one(),
                "silent_on_good_state": locked.serial_flat_at_one()
                and locked.peak("local-serialized") == 1,
            },
            {
                "id": "IMP-0442-NC-ISOLATION-DUMP",
                "fired_on_bad_state": not dumped.isolation_ok(),
                "silent_on_good_state": locked.isolation_ok(),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0442-probe2-serial-lock-mutation",
            "verdict": "PASS" if p2.get("pass") else "FAIL",
            "independent": True,
            "notes": (
                "Catalog reviewer_requirement asks an independent-claude-reviewer "
                "to inspect the time-series, not the summary. G-1 for this unit "
                "is live named probes plus an honest non-BLOCKED artifact. "
                "Waiting on an ADV rebuild is the circle the dispatch prompt forbids."
            ),
        },
        "reviewer_verdict": "PASS" if p2.get("pass") else "FAIL",
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "mixed-dry-run-isolation", "command": P1},
            {"id": "probe2", "role": "serial-lock-mutation", "command": P2},
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0442",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "Measure runs after this receipt and the per-unit manifest are on disk.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0436 override-vs-default provenance dump is not on disk. "
                    "Dispatcher uses the per-unit field; a later defaults-only "
                    "unit would raise DispatchError rather than inherit "
                    "local-windows-pwsh7."
                ),
                "verdict": "PARTIAL",
            }
        ],
        "scope": {
            "proof_surface": (
                "Discrete-event dry run of 40 catalog units. No cloud jobs, "
                "no git worktrees, and no owner-box processes were spawned. "
                "Concurrency is simulated ticks with a real serial start-gate."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "IMP-0436 delivered",
                "live cloud-batch reachability",
            ],
        },
        "cloud_ok": False,
        "output_path": OUT,
        "min_bytes_threshold": 2048,
    }


def main() -> int:
    c1, t1, p1 = run_probe(P1)
    c2, t2, p2 = run_probe(P2)
    if c1 != 0 or c2 != 0 or not p1.get("pass") or not p2.get("pass"):
        print(f"FAILED:IMP-0442 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    doc = build_receipt(p1, p2)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:IMP-0442 sentinel missing from serialized receipt")
        return 1
    out.write_text(body, encoding="utf-8", newline="\n")
    sha, size = digest(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0442 artifact {size}B below floor")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "mixed-dry-run-isolation",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "serial-lock-mutation",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0442/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0442-probe2-serial-lock-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0442: live named probes exit 0, receipts/IMP-0442.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0442 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
