#!/usr/bin/env python3
"""IMP-0413 probe 2: removing one signal turns the live-but-idle test red.

Honest two-signal AND-gate HOLDs a live-but-idle session. A source mutation
that drops the process signal (MIN_SIGNALS=1, REQUIRED_SIGNALS=bytes-only)
proves death on the same idle fixture — the live-but-idle assertion fails.
The honest API also refuses a single-signal death verdict. AST confirms
the AND-gate cardinality is in the shipped source, not only in this probe.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIB = REPO / "command-center" / "lib"
SRC = LIB / "orphan_reaper" / "liveness.py"
sys.path.insert(0, str(LIB))

from orphan_reaper.liveness import (  # noqa: E402
    IDLE_WINDOW_SECONDS,
    MIN_SIGNALS,
    REQUIRED_SIGNALS,
    SIGNAL_BYTES,
    SIGNAL_PROCESS,
    SingleSignalDeathError,
    death_and_gate,
    observe_bytes,
    observe_process,
    proof_of_death,
)

ART = REPO / "command-center" / "receipts" / "IMP-0413.json"
SENTINEL = "SENTINEL:IMP-0413:REAPER-PROOF-OF-DEATH"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0413-probe2 {msg}")
    return 1


def ast_gate_ok(tree: ast.AST) -> tuple[bool, str]:
    min_ok = False
    required_ok = False
    proof_calls_pair = False
    mtime_raises = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MIN_SIGNALS":
                    if isinstance(node.value, ast.Constant) and node.value.value == 2:
                        min_ok = True
                if isinstance(target, ast.Name) and target.id == "REQUIRED_SIGNALS":
                    text = ast.dump(node.value)
                    if "SIGNAL_PROCESS" in text and "SIGNAL_BYTES" in text:
                        required_ok = True
        if isinstance(node, ast.FunctionDef) and node.name == "proof_of_death":
            called = {
                n.func.id
                for n in ast.walk(node)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            }
            if "require_named_pair" in called and "forbid_mtime" in called:
                if "death_and_gate" in called:
                    proof_calls_pair = True
        if isinstance(node, ast.Raise):
            exc = node.exc
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                if exc.func.id == "MtimeSignalUnrepresentable":
                    mtime_raises = True
    if not min_ok:
        return False, "MIN_SIGNALS is not 2 in source"
    if not required_ok:
        return False, "REQUIRED_SIGNALS does not name both process and bytes"
    if not proof_calls_pair:
        return False, "proof_of_death does not AND-gate via require_named_pair"
    if not mtime_raises:
        return False, "MtimeSignalUnrepresentable is never raised"
    return True, "MIN_SIGNALS=2 REQUIRED both names AND-gate mtime-raise"


def load_mutant(src: str):
    mutated = src.replace("MIN_SIGNALS = 2", "MIN_SIGNALS = 1", 1)
    mutated = mutated.replace(
        "REQUIRED_SIGNALS = frozenset({SIGNAL_PROCESS, SIGNAL_BYTES})",
        "REQUIRED_SIGNALS = frozenset({SIGNAL_BYTES})",
        1,
    )
    if mutated == src:
        raise RuntimeError("mutation did not change source; fingerprints would match")
    ns: dict[str, object] = {}
    exec(compile(mutated, "liveness_mutant.py", "exec"), ns)
    return ns, mutated


def main() -> int:
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared:{doc.get('state')}")
        if SENTINEL not in text:
            return fail("sentinel-absent")

    src = SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    ok, why = ast_gate_ok(tree)
    if not ok:
        return fail(why)

    if MIN_SIGNALS != 2:
        return fail(f"runtime MIN_SIGNALS={MIN_SIGNALS}")
    if REQUIRED_SIGNALS != frozenset({SIGNAL_PROCESS, SIGNAL_BYTES}):
        return fail(f"runtime REQUIRED_SIGNALS={REQUIRED_SIGNALS}")

    idle_proc = observe_process(pid_exists=True, cpu_delta_ns=0, pid=1)
    idle_bytes = observe_bytes(bytes_t0=4096, bytes_t1=4096)
    honest = proof_of_death(
        (idle_proc, idle_bytes),
        session_id="sess-live-idle",
        window_seconds=IDLE_WINDOW_SECONDS,
    )
    live_idle_honest_pass = (not honest.death_proven) and honest.action == "HOLD"
    if not live_idle_honest_pass:
        return fail(f"honest live-but-idle did not HOLD: {honest.to_dict()}")

    try:
        proof_of_death((idle_bytes,))
        return fail("honest API accepted a single-signal death verdict")
    except SingleSignalDeathError:
        single_refused = True

    # Same idle bytes, cardinality bypassed: AND-gate over one NOT-ALIVE signal.
    mutant_bypass_would_reap = death_and_gate((idle_bytes,))
    if not mutant_bypass_would_reap:
        return fail("bytes-only AND-gate did not prove death; mutation control inert")

    ns, mutated = load_mutant(src)
    mutant_observe_bytes = ns["observe_bytes"]
    mutant_proof = ns["proof_of_death"]
    mutant_bytes = mutant_observe_bytes(bytes_t0=4096, bytes_t1=4096)
    mutant_report = mutant_proof((mutant_bytes,), session_id="sess-live-idle")
    live_idle_mutant_red = bool(mutant_report.death_proven) and mutant_report.action == "REAP"
    if not live_idle_mutant_red:
        return fail(
            f"mutation did not turn live-but-idle red: {mutant_report}"
        )

    # Dead session still reaps on the honest path (both NOT-ALIVE).
    dead = proof_of_death(
        (
            observe_process(pid_exists=False, cpu_delta_ns=0, pid=9),
            observe_bytes(bytes_t0=2048, bytes_t1=2048),
        ),
        session_id="sess-dead",
    )
    if not dead.death_proven or dead.action != "REAP":
        return fail(f"honest dead session not reaped: {dead.to_dict()}")

    payload = {
        "pass": True,
        "probe": "probe2-signal-mutation",
        "unit_id": "IMP-0413",
        "ast_ok": True,
        "ast_why": why,
        "live_idle_honest_pass": True,
        "live_idle_mutant_red": True,
        "single_signal_refused": single_refused,
        "bytes_only_and_gate_would_reap": mutant_bypass_would_reap,
        "mutant_min_signals": ns["MIN_SIGNALS"],
        "mutant_required": sorted(ns["REQUIRED_SIGNALS"]),
        "source_bytes": len(src.encode("utf-8")),
        "mutant_bytes": len(mutated.encode("utf-8")),
        "honest_dead_reaped": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "honest_idle=HOLD mutant_idle=REAP single_refused=True "
        f"ast_ok=True min={MIN_SIGNALS}"
    )
    print("SUCCESS:IMP-0413-probe2 one-signal mutation turns live-but-idle red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
