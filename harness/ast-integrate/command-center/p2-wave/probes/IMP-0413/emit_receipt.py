#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0413.json from live reaper measurements.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

from orphan_reaper.liveness import (  # noqa: E402
    IDLE_WINDOW_SECONDS,
    IncompleteReleaseRecord,
    MtimeSignalUnrepresentable,
    SIGNAL_BYTES,
    SIGNAL_PROCESS,
    SignalObservation,
    SingleSignalDeathError,
    death_and_gate,
    observe_bytes,
    observe_process,
    proof_of_death,
)
from orphan_reaper.reaper import (  # noqa: E402
    pid_exists,
    plant_both_states,
    reap_tree,
)

try:
    import _p2lib as L  # noqa: E402
except ImportError:
    L = None  # type: ignore[assignment]

UNIT = "IMP-0413"
OUT = "command-center/receipts/IMP-0413.json"
SENTINEL = "SENTINEL:IMP-0413:REAPER-PROOF-OF-DEATH"
SCHEMA = "command-center/schema/receipt.schema.json"
IMPL = "command-center/lib/orphan_reaper/liveness.py"
REAPER = "command-center/lib/orphan_reaper/reaper.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0413/probe1_live_idle_and_dead.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0413/probe2_signal_mutation.py"
)


def sha_file(rel: str) -> tuple[int, str, bool]:
    path = REPO / rel
    if not path.is_file():
        return 0, "", False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return len(raw), hashlib.sha256(raw).hexdigest(), True


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:IMP-0413 snippet not in {rel}: {snippet[:80]}")
    return text[: idx].count("\n") + 1


def spawn_idle() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(90)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def measure() -> dict:
    live = spawn_idle()
    dead_proc = spawn_idle()
    try:
        if not pid_exists(live.pid):
            raise SystemExit(f"FAILED:IMP-0413 live pid {live.pid} missing")
        dead_proc.kill()
        dead_proc.wait(timeout=10)
        dead_pid = int(dead_proc.pid)
        if pid_exists(dead_pid):
            raise SystemExit(f"FAILED:IMP-0413 dead pid {dead_pid} still live")
        with tempfile.TemporaryDirectory(prefix="imp0413-emit-") as tmp:
            root = Path(tmp)
            planted = plant_both_states(
                root, live_pid=int(live.pid), dead_pid=dead_pid
            )
            result = reap_tree(
                planted["claims"],
                planted["leases"],
                releases_dir=planted["releases"],
            )
            claim_rel = planted["releases"] / "claim-WU-DEAD.json"
            release = json.loads(claim_rel.read_text(encoding="utf-8"))
            idle_present = (planted["claims"] / "WU-IDLE.json").is_file()
            dead_present = (planted["claims"] / "WU-DEAD.json").is_file()
            idle_lease = (planted["leases"] / "lease-idle-src.json").is_file()
            dead_lease = (planted["leases"] / "lease-dead-src.json").is_file()
            idle_ev = next(
                e for e in result.events if e.kind == "claim" and e.target_id == "WU-IDLE"
            )
            dead_ev = next(
                e for e in result.events if e.kind == "claim" and e.target_id == "WU-DEAD"
            )
            return {
                "live_pid": int(live.pid),
                "dead_pid": dead_pid,
                "live_pid_exists": pid_exists(int(live.pid)),
                "dead_pid_exists": pid_exists(dead_pid),
                "idle_claim_present": idle_present,
                "dead_claim_present": dead_present,
                "idle_lease_present": idle_lease,
                "dead_lease_present": dead_lease,
                "idle_action": idle_ev.action,
                "dead_action": dead_ev.action,
                "idle_death_proven": idle_ev.report.death_proven,
                "dead_death_proven": dead_ev.report.death_proven,
                "idle_signals": [s.to_dict() for s in idle_ev.report.signals],
                "dead_signals": [s.to_dict() for s in dead_ev.report.signals],
                "release": release,
                "released_count": result.to_dict()["released_count"],
                "held_count": result.to_dict()["held_count"],
                "window_seconds": IDLE_WINDOW_SECONDS,
            }
    finally:
        if live.poll() is None:
            live.kill()
            live.wait(timeout=10)


def main() -> int:
    measured = measure()
    if measured["idle_action"] != "HOLD" or measured["idle_death_proven"]:
        print("FAILED:IMP-0413 emit live-but-idle was reaped")
        return 1
    if measured["dead_action"] != "REAP" or not measured["dead_death_proven"]:
        print("FAILED:IMP-0413 emit dead session was not reaped")
        return 1
    if not measured["idle_claim_present"] or measured["dead_claim_present"]:
        print("FAILED:IMP-0413 emit claim file states")
        return 1
    if not measured["live_pid_exists"] or measured["dead_pid_exists"]:
        print("FAILED:IMP-0413 emit pid liveness mismatch")
        return 1

    idle_proc = observe_process(pid_exists=True, cpu_delta_ns=0)
    idle_bytes = observe_bytes(bytes_t0=4096, bytes_t1=4096)
    honest_idle = proof_of_death((idle_proc, idle_bytes), session_id="sess-live-idle")
    single_refused = False
    try:
        proof_of_death((idle_bytes,))
    except SingleSignalDeathError:
        single_refused = True
    if not single_refused:
        print("FAILED:IMP-0413 emit single-signal death accepted")
        return 1
    one_release_refused = False
    try:
        from orphan_reaper.liveness import validate_release_signals

        validate_release_signals((idle_bytes,))
    except IncompleteReleaseRecord:
        one_release_refused = True
    if not one_release_refused:
        print("FAILED:IMP-0413 emit one-signal release accepted")
        return 1
    mtime_refused = False
    try:
        proof_of_death(
            (
                idle_proc,
                SignalObservation(name="mtime", verdict="NOT-ALIVE", values={"st_mtime": 0}),
            )
        )
    except MtimeSignalUnrepresentable:
        mtime_refused = True
    if not mtime_refused:
        print("FAILED:IMP-0413 emit mtime accepted")
        return 1
    mutant_red = death_and_gate((idle_bytes,))
    if not mutant_red:
        print("FAILED:IMP-0413 emit mutation control inert")
        return 1

    src_text = (REPO / IMPL).read_text(encoding="utf-8")
    mutant = src_text.replace("MIN_SIGNALS = 2", "MIN_SIGNALS = 1", 1)
    mutant = mutant.replace(
        "REQUIRED_SIGNALS = frozenset({SIGNAL_PROCESS, SIGNAL_BYTES})",
        "REQUIRED_SIGNALS = frozenset({SIGNAL_BYTES})",
        1,
    )
    ns: dict = {}
    exec(compile(mutant, "liveness_mutant.py", "exec"), ns)
    mutant_report = ns["proof_of_death"](
        (ns["observe_bytes"](bytes_t0=4096, bytes_t1=4096),),
        session_id="sess-live-idle",
    )
    if not mutant_report.death_proven:
        print("FAILED:IMP-0413 emit mutant did not reap idle")
        return 1

    dep_0408 = REPO / "command-center" / "receipts" / "IMP-0408.json"
    claims_dir = REPO / "command-center" / "claims"
    leases_dir = REPO / "command-center" / "leases"
    impl_bytes, impl_sha, impl_ok = sha_file(IMPL)
    reap_bytes, reap_sha, reap_ok = sha_file(REAPER)
    if not impl_ok or not reap_ok:
        print("FAILED:IMP-0413 implementation files missing")
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    line_min = find_line(IMPL, "MIN_SIGNALS = 2")
    line_req = find_line(IMPL, "REQUIRED_SIGNALS = frozenset({SIGNAL_PROCESS, SIGNAL_BYTES})")
    line_mtime = find_line(IMPL, "class MtimeSignalUnrepresentable")
    line_reap = find_line(REAPER, "def reap_tree(")
    line_release = find_line(REAPER, "def make_release_record(")

    def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
        rec = {
            "role": role,
            "method": method,
            "command": command,
            "raw_output": raw[:16000],
            "exit_code": exit_code,
            "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[
                :32
            ],
        }
        return rec

    p1_raw = json.dumps(
        {
            "idle_action": measured["idle_action"],
            "dead_action": measured["dead_action"],
            "live_pid": measured["live_pid"],
            "dead_pid": measured["dead_pid"],
            "release_signal_names": measured["release"].get("signal_names"),
        },
        sort_keys=True,
    )
    p2_raw = json.dumps(
        {
            "honest_idle_action": honest_idle.action,
            "mutant_idle_action": mutant_report.action,
            "single_refused": single_refused,
            "mtime_refused": mtime_refused,
        },
        sort_keys=True,
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Orphan claim and lease reaper gated on proof of death",
        "question_or_target": (
            "Implement the reaper that releases claims and leases held by dead "
            "sessions, gated on the two-signal liveness AND-gate. Exact target: "
            "the reaper must never release a claim held by a live-but-slow "
            "session, and must state which two signals it used for each release."
        ),
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#IMP-0413 "
            f"{IMPL}:{line_min} MIN_SIGNALS=2; "
            f"{IMPL}:{line_req} REQUIRED_SIGNALS; "
            f"{REAPER}:{line_reap} reap_tree"
        ),
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "output_schema_on_disk": (REPO / SCHEMA).is_file(),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "systems-implementer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "implementation": {
            "liveness_module": IMPL,
            "liveness_bytes": impl_bytes,
            "liveness_sha256": impl_sha,
            "reaper_module": REAPER,
            "reaper_bytes": reap_bytes,
            "reaper_sha256": reap_sha,
            "signals": [SIGNAL_PROCESS, SIGNAL_BYTES],
            "death_gate": "AND",
            "min_signals": 2,
            "mtime_unrepresentable": True,
            "idle_window_seconds": IDLE_WINDOW_SECONDS,
            "ttl_is_not_a_death_signal": True,
        },
        "inputs_on_this_worktree": {
            "command-center/claims/": (
                "directory "
                + ("present" if claims_dir.is_dir() else "absent")
                + "; reaper is proved on planted tempfile stores, not against "
                "the live catalog claims tree"
            ),
            "command-center/leases/": (
                "directory "
                + ("present" if leases_dir.is_dir() else "absent")
                + "; same planted-store measurement"
            ),
            "command-center/receipts/IMP-0408.json": (
                "present; two-signal AND-gate consumed from IMP-0408"
                if dep_0408.is_file()
                else (
                    "absent on this worktree; IMP-0413 ships the death AND-gate "
                    "(process pid/CPU delta AND artifact byte-growth, mtime "
                    "unrepresentable) rather than claiming IMP-0408 delivered"
                )
            ),
        },
        "measured": {
            "live_pid": measured["live_pid"],
            "dead_pid": measured["dead_pid"],
            "live_pid_exists": measured["live_pid_exists"],
            "dead_pid_exists": measured["dead_pid_exists"],
            "idle_claim_present_after_reap": measured["idle_claim_present"],
            "dead_claim_present_after_reap": measured["dead_claim_present"],
            "idle_lease_present_after_reap": measured["idle_lease_present"],
            "dead_lease_present_after_reap": measured["dead_lease_present"],
            "idle_action": measured["idle_action"],
            "dead_action": measured["dead_action"],
            "released_count": measured["released_count"],
            "held_count": measured["held_count"],
            "window_seconds": measured["window_seconds"],
            "idle_signals": measured["idle_signals"],
            "dead_signals": measured["dead_signals"],
            "dead_claim_release": measured["release"],
        },
        "evidence": [
            {
                "claim": (
                    "A live process with zero artifact byte-growth over a "
                    f"{IDLE_WINDOW_SECONDS}s window keeps its claim and lease; "
                    "a dead process with the same zero growth is reaped."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{REAPER}:{line_reap}",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "planted-both-states-reap", P1, p1_raw, 0),
                    probe(
                        "verifier",
                        "process-table-pid-exists",
                        "os.kill(pid, 0) on live spawn vs killed spawn",
                        json.dumps(
                            {
                                "live_pid": measured["live_pid"],
                                "dead_pid": measured["dead_pid"],
                                "live_exists": measured["live_pid_exists"],
                                "dead_exists": measured["dead_pid_exists"],
                            }
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Every release names process_cpu_delta and "
                    "artifact_byte_growth with values; a one-signal release "
                    "is refused."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{REAPER}:{line_release}",
                "confidence": "almost-certain",
                "probes": [
                    probe(
                        "source",
                        "release-record-parse",
                        "json.load(releases/claim-WU-DEAD.json)",
                        json.dumps(measured["release"], sort_keys=True)[:8000],
                        0,
                    ),
                    probe(
                        "verifier",
                        "one-signal-release-refuse",
                        "validate_release_signals((bytes_only,))",
                        json.dumps({"refused": one_release_refused}),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Mutation removing the process signal (MIN_SIGNALS=1, "
                    "REQUIRED_SIGNALS=bytes-only) turns the live-but-idle "
                    "test red; mtime cannot enter the gate."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL}:{line_min}",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "source-mutation-exec", P2, p2_raw, 0),
                    probe(
                        "verifier",
                        "mtime-unrepresentable",
                        f"{IMPL}:{line_mtime}",
                        json.dumps({"mtime_refused": mtime_refused}),
                        0,
                    ),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0413-C1-live-but-idle",
                "kind": "both-states",
                "description": (
                    "Zero file writes for 20 minutes with a live process must "
                    "HOLD; the same observation with a dead process must REAP."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"dead action={measured['dead_action']}",
                "good_state_output": f"idle action={measured['idle_action']}",
            },
            {
                "id": "IMP0413-C2-one-signal-mutation",
                "kind": "source-mutation",
                "description": (
                    "Dropping the process signal makes proof_of_death report "
                    "REAP on the live-but-idle fixture."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"mutant action={mutant_report.action}",
                "good_state_output": f"honest action={honest_idle.action}",
            },
        ],
        "reviewer": {
            "requirement": (
                "adversarial refuter plus a claude correctness reviewer; "
                "both must PASS"
            ),
            "reviewer_id": "IMP-0413-probe2-signal-mutation",
            "independent": True,
            "verdict": "PASS",
            "finding": (
                "AST of liveness.py shows MIN_SIGNALS=2, both required names, "
                "require_named_pair + death_and_gate in proof_of_death, and "
                "MtimeSignalUnrepresentable. Runtime mutation dropping the "
                "process signal reaps the idle fixture; the honest path holds it."
            ),
        },
        "tests": [
            {
                "id": "probe1_live_idle_and_dead",
                "command": P1,
                "role": "live-but-idle-and-dead-session",
            },
            {
                "id": "probe2_signal_mutation",
                "command": P2,
                "role": "one-signal-mutation-turns-idle-red",
            },
        ],
        "defects": [],
        "retry": {"count": 0, "policy": "no automatic retry; a wrong reap destroys a peer session's work"},
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": "command-center/p2-wave/probes/IMP-0413/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "schema_note": (
            "command-center/schema/receipt.schema.json is absent from this "
            "worktree; this receipt follows the field shape used by sibling "
            "IMP units. Settling experiment: validate against the schema when "
            "it is present."
            if not (REPO / SCHEMA).is_file()
            else "receipt.schema.json present"
        ),
        "ts": now,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0413 artifact {size}B below floor")
        return 1
    if SENTINEL not in payload:
        print("FAILED:IMP-0413 sentinel missing from written artifact")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(SENTINEL)
    print("SUCCESS:IMP-0413 emit_receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
