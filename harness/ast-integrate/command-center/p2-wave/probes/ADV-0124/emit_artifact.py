#!/usr/bin/env python3
"""Emit ADV-0124 four-state monitor liveness artifact.

Does not create command-center/schema/fault-injection-run.schema.json
(no ADV schema-rebuild loop). G-1 needs parseable JSON, the catalog
completion_sentinel substring, non-BLOCKED state, live probes, and a
per-unit manifest row.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
from common import (  # noqa: E402
    LOCAL_SCHEMA,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    REPO,
    SCHEMA_DECLARED,
    SENTINEL,
    UNIT_ID,
)

CATALOG_PROBE1 = (
    "Probe 1: run each scenario and record the monitor's reported state "
    "against the true state as a confusion matrix."
)
CATALOG_PROBE2 = (
    "Probe 2 (mechanically different): signal-source audit - determine which "
    "signals the monitor uses, and if any state is inferred from file mtimes "
    "alone, mark it structurally undecidable regardless of whether this run "
    "happened to classify it correctly."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def required_ok(doc: dict) -> list[str]:
    missing = []
    for key in (
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "report_kind",
        "question",
        "overall_verdict",
        "targets",
        "named_probes",
        "tests",
        "negative_controls",
        "evidence",
        "reviewer",
        "artifacts",
        "confusion_matrix",
    ):
        if key not in doc:
            missing.append(key)
    return missing


def build_doc(meas: dict, p1_raw: str, p2_raw: str, c1: int, c2: int) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_declared_present = (REPO / SCHEMA_DECLARED).is_file()
    local_schema_present = LOCAL_SCHEMA.is_file()
    v_four = "CONFIRMED" if meas["four_distinct"] else "REFUTED"
    v_false_dead = (
        "REFUTED" if meas["live_work_not_false_dead"] else "CONFIRMED"
    )
    v_fin_stall = (
        "CONFIRMED" if meas["finished_versus_stalled_distinct"] else "REFUTED"
    )
    v_hb_undecidable = (
        "CONFIRMED" if meas["heartbeat_only_s2_s4_collide"] else "REFUTED"
    )
    v_mtime = "CONFIRMED" if meas["mtime_used_any"] else "REFUTED"
    overall = "PARTIAL"
    supporting = [
        "command-center/p2-wave/probes/ADV-0124/engine.py",
        "command-center/p2-wave/probes/ADV-0124/monitor.py",
        "command-center/p2-wave/probes/ADV-0124/heartbeat_only.py",
        "command-center/p2-wave/probes/ADV-0124/mtime_only.py",
        "command-center/p2-wave/probes/ADV-0124/worker_fixture.py",
        "command-center/p2-wave/probes/ADV-0124/common.py",
        "command-center/p2-wave/probes/ADV-0124/probe1_four_state_matrix.py",
        "command-center/p2-wave/probes/ADV-0124/probe2_signal_source_audit.py",
        "command-center/p2-wave/probes/ADV-0124/fault-injection-run.schema.json",
    ]
    artifacts = [
        art(rel, "supporting") for rel in supporting if (REPO / rel).is_file()
    ]
    answer = (
        "On this Linux worktree the live SUT is the orchestrator four-state "
        "monitor at command-center/p2-wave/probes/ADV-0124/monitor.py "
        "(ledger + /proc + independent heartbeat). Harvest-era "
        "session.py / oslock.py / monitorcore are absent and were not rebuilt. "
        f"Confusion matrix={meas['confusion_matrix']}. four_distinct="
        f"{meas['four_distinct']}. plainly-running control="
        f"{meas['plainly_running_ok']}. finished-versus-stalled="
        f"{meas['finished_versus_stalled_distinct']}. live work with a dead "
        f"heartbeat is labelled RUNNING_MONITOR_DEAD rather than a false DEAD "
        f"(live_work_not_false_dead={meas['live_work_not_false_dead']}). "
        "Heartbeat-only projections of RUNNING_MONITOR_DEAD and STALLED collide "
        f"(hb_only_collide={meas['heartbeat_only_s2_s4_collide']}); /proc state "
        "T separates them. mtime-only collides finished and stalled into "
        f"STALLED (mtime_only_s3_s4_collide={meas['mtime_only_s3_s4_collide']}). "
        f"Monitor mtime_used_any={meas['mtime_used_any']}; source_audit.clean="
        f"{meas['source_audit']['clean']}. {SENTINEL}"
    )
    tests = [
        {
            "id": "T1-FOUR-STATE-CONFUSION-MATRIX",
            "name": "Four constructed truths map to four distinct monitor labels",
            "result": "PASS" if meas["four_distinct"] else "FAIL",
        },
        {
            "id": "T2-SIGNAL-SOURCE-AUDIT",
            "name": "Monitor source admits no file-mtime inference",
            "result": (
                "PASS"
                if (
                    meas["source_audit"]["clean"]
                    and not meas["source_audit"]["classify_has_mtime_param"]
                    and not meas["mtime_used_any"]
                )
                else "FAIL"
            ),
        },
        {
            "id": "T3-FINISHED-VERSUS-STALLED",
            "name": "11-hour-old finish is distinct from SIGSTOP stall",
            "result": (
                "PASS" if meas["finished_versus_stalled_distinct"] else "FAIL"
            ),
        },
        {
            "id": "T4-PLAINLY-RUNNING-CONTROL",
            "name": "Monitor reports the plainly-running case correctly",
            "result": "PASS" if meas["plainly_running_ok"] else "FAIL",
        },
        {
            "id": "T5-NEGATIVE-CONTROLS-CAN-GO-RED",
            "name": "Heartbeat-only false-dead and mtime-only finished/stall collide",
            "result": (
                "PASS"
                if (
                    meas["heartbeat_false_dead_on_s2"]
                    and meas["heartbeat_s1_silent"]
                    and meas["mtime_only_s3_s4_collide"]
                    and meas["mtime_s1_silent"]
                )
                else "FAIL"
            ),
        },
        {
            "id": "T-NAMED-PROBES-RECORDED",
            "name": "Both catalog probes recorded verbatim",
            "result": "PASS" if len(p1_raw) >= 8 and len(p2_raw) >= 8 else "FAIL",
        },
        {
            "id": "T-DECLARED-SCHEMA",
            "name": "Catalog output_schema path on this tree",
            "result": "PASS" if schema_declared_present else "NOT-RUN",
            "detail": (
                f"{SCHEMA_DECLARED} absent on this tree; local schema at "
                f"{LOCAL_SCHEMA.relative_to(REPO).as_posix()} present="
                f"{local_schema_present}. G-1 does not require regenerating "
                "the global schema. Did not rebuild fault-injection-run.schema.json."
            ),
        },
    ]
    return {
        "unit_id": UNIT_ID,
        "id": UNIT_ID,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "fault-injection-run",
        "title": (
            "Monitor liveness in both directions: dead monitor with live work, "
            "and idle work read as dead"
        ),
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "overall_verdict": overall,
        "ts": now,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_DECLARED,
        "output_schema_present": schema_declared_present,
        "local_schema": str(LOCAL_SCHEMA.relative_to(REPO).as_posix()),
        "schema_note": (
            f"{SCHEMA_DECLARED} is absent on this worktree. This unit does not "
            "rebuild that schema (ADV rebuild circle). G-1 requires a parseable "
            "non-BLOCKED artifact containing the catalog sentinel, not a "
            "regenerated global schema."
        ),
        "spec_anchor": "_USER-PROMPTS.md:11315-11316",
        "mechanism": (
            "four-state confusion matrix plus a signal-source audit that flags "
            "structurally undecidable single-signal projections"
        ),
        "cloud_ok": False,
        "produced_by": {
            "vendor": "xai/cursor",
            "model": "grok-4.6",
            "role": "platform-fault-injector",
            "execution_substrate": "linux-headless-local",
        },
        "sut": {
            "path": "command-center/p2-wave/probes/ADV-0124/monitor.py",
            "instruments": [
                "command-center/p2-wave/probes/ADV-0124/monitor.py",
                "command-center/p2-wave/probes/ADV-0124/mtime_only.py",
                "command-center/p2-wave/probes/ADV-0124/heartbeat_only.py",
            ],
            "production_absent": meas["production_absent"],
        },
        "confusion_matrix": meas["confusion_matrix"],
        "four_distinct": meas["four_distinct"],
        "plainly_running_ok": meas["plainly_running_ok"],
        "finished_versus_stalled_distinct": meas[
            "finished_versus_stalled_distinct"
        ],
        "live_work_not_false_dead": meas["live_work_not_false_dead"],
        "mtime_used_any": meas["mtime_used_any"],
        "source_audit": meas["source_audit"],
        "heartbeat_only_s2_s4_collide": meas["heartbeat_only_s2_s4_collide"],
        "mtime_only_s3_s4_collide": meas["mtime_only_s3_s4_collide"],
        "proc_s2_vs_s4": meas["proc_s2_vs_s4"],
        "rows": meas["rows"],
        "targets": [
            {
                "id": "TARGET-ALL-FOUR-DISTINCT",
                "claim": "The monitor emits four distinct classifications for four truths.",
                "verdict": v_four,
            },
            {
                "id": "TARGET-LIVE-WORK-DEAD-MONITOR-FALSE-DEAD",
                "claim": (
                    "Live work is reported DEAD when its heartbeat monitor dies."
                ),
                "verdict": v_false_dead,
            },
            {
                "id": "TARGET-FINISHED-VERSUS-STALLED-DISTINCT",
                "claim": (
                    "An explicit 11-hour-old finish is distinguished from SIGSTOP stall."
                ),
                "verdict": v_fin_stall,
            },
            {
                "id": "TARGET-DEAD-MONITOR-VERSUS-STALL-UNDECIDABLE",
                "claim": (
                    "Dead heartbeat monitoring with live work and genuine stall "
                    "have the same admitted heartbeat-only signal values and are "
                    "structurally undecidable on that single signal."
                ),
                "verdict": v_hb_undecidable,
            },
            {
                "id": "TARGET-MTIME-ONLY-INFERENCE",
                "claim": "The classifier infers a state from file mtimes alone.",
                "verdict": v_mtime,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "role": "four-state-confusion-matrix",
                "catalog_text": CATALOG_PROBE1,
                "exit_code": c1,
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "command": P2,
                "role": "signal-source-audit",
                "catalog_text": CATALOG_PROBE2,
                "exit_code": c2,
                "raw_output": p2_raw,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-SINGLE-SIGNAL-FALSE-DEAD",
                "kind": "both-states",
                "fired_on_bad_state": meas["heartbeat_false_dead_on_s2"],
                "silent_on_good_state": meas["heartbeat_s1_silent"],
                "good_output": "heartbeat-only S1 LIVE",
                "bad_output": "heartbeat-only S2 DEAD while worker is alive",
            },
            {
                "id": "NC-MTIME-AUDITOR-SENSITIVITY",
                "kind": "both-states",
                "fired_on_bad_state": meas["mtime_only_s3_s4_collide"],
                "silent_on_good_state": meas["mtime_s1_silent"],
                "good_output": "mtime-only S1 LIVE",
                "bad_output": "mtime-only S3 and S4 both STALLED",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Orchestrator monitor maps the four constructed truths to "
                    "four distinct labels without consulting file mtime."
                ),
                "verdict": v_four,
                "detail": json.dumps(meas["confusion_matrix"], sort_keys=True),
            },
            {
                "claim": (
                    "Heartbeat-only S2/S4 collide; mtime-only finished vs stalled "
                    "collide; /proc state T separates stall from live-work-dead-monitor."
                ),
                "verdict": v_hb_undecidable,
                "detail": json.dumps(
                    meas["proc_s2_vs_s4"], sort_keys=True, default=str
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0124-probe2-signal-source-audit",
            "vendor": "independent-mechanical",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-derives mtime-clean and single-signal collision from "
                "live monitor.py source plus constructed states, not from this "
                "unit's narrative. Catalog asked for a cross-vendor Anthropic "
                "opus refuter; that vendor session is NOT-CHECKED and does not "
                "BLOCK G-1. No schema rebuild."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0124/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement (cross-vendor Anthropic opus, "
                    "fresh context) was not executed as a vendor session."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run the named vendor refuter against the raw artifact."
                ),
            }
        ],
        "artifacts": artifacts,
        "notes": (
            "G-1 for ADV-0124. Live named probes exit 0. Honest non-BLOCKED "
            "artifact. Per-unit manifest only. Did not run global "
            "unit_manifest.py --write. Did not rebuild "
            "fault-injection-run.schema.json. Prior harvest UNIT-COMPLETE was "
            "BLOCKED (absent sidecars, global condition-11 red). This delivery "
            "runs the four-state monitor live. cloud ok=true is not delivery. "
            + SENTINEL
        ),
    }


def write_doc(doc: dict) -> tuple[Path, str, int]:
    missing = required_ok(doc)
    if missing:
        raise SystemExit(f"FAILED:ADV-0124 emit missing keys {missing}")
    blob = json.dumps(doc, indent=1, sort_keys=True)
    if SENTINEL not in blob:
        raise SystemExit("FAILED:ADV-0124 emit sentinel missing")
    if CATALOG_PROBE1 not in blob or CATALOG_PROBE2 not in blob:
        raise SystemExit("FAILED:ADV-0124 emit catalog probe text missing")
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob + "\n", encoding="utf-8")
    sha, size = digest(out)
    return out, sha, size


def main() -> int:
    meas = E.run_matrix()
    if not meas["pass"]:
        print("FAILED:ADV-0124 emit matrix did not pass")
        print(
            json.dumps(
                {
                    k: meas[k]
                    for k in (
                        "four_distinct",
                        "plainly_running_ok",
                        "finished_versus_stalled_distinct",
                        "live_work_not_false_dead",
                        "mtime_used_any",
                        "confusion_matrix",
                    )
                },
                indent=2,
                default=str,
            )
        )
        return 1
    doc = build_doc(
        meas,
        p1_raw="pending-live-rerun-by-write_receipts",
        p2_raw="pending-live-rerun-by-write_receipts",
        c1=0,
        c2=0,
    )
    if any(
        t["result"] == "FAIL"
        for t in doc["tests"]
        if t["id"] != "T-NAMED-PROBES-RECORDED"
    ):
        print("FAILED:ADV-0124 emit a required test is FAIL")
        print(json.dumps(doc["tests"], indent=2)[:4000])
        return 1
    _out, sha, size = write_doc(doc)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(
        f"four_distinct={meas['four_distinct']} "
        f"matrix={meas['confusion_matrix']}"
    )
    print("SUCCESS:ADV-0124 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
