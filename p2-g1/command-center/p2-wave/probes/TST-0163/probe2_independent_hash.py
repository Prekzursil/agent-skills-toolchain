#!/usr/bin/env python3
"""Probe 2 (reviewer): recompute both hashes in a fresh process; naive mutant misses.

Mechanically different from probe 1: this probe does not author the launcher
compare_mode. It writes saved dispatch-spec bytes to a temp file, invokes
hash_spec.py as a child process, and checks that CONTRACT-DRIFT names those
two digests. It also re-runs the last-write-wins mutant to prove contradictory
tool_call_cap values stay live without per-unit comparison.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from launcher import independent_digest  # noqa: E402

ART = REPO / "command-center/receipts/TST-0163.json"
UNIT = "TST-0163"
HASHER = HERE / "hash_spec.py"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def hash_text_via_child(text: str) -> tuple[str, int]:
    with tempfile.TemporaryDirectory(prefix="tst0163-p2-") as td:
        path = Path(td) / "spec.json"
        path.write_text(text, encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-B", str(HASHER), str(path)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"hash_spec.py rc={proc.returncode} {proc.stderr}")
        digest = (proc.stdout or "").strip().splitlines()[-1].strip()
        pid = 0
        for line in (proc.stderr or "").splitlines():
            if line.startswith("pid="):
                pid = int(line.split("=", 1)[1])
        return digest, pid


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0163" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    edited = S.run_cohort(detect=True, edit=True)
    naive = S.test_naive_last_write_wins_leaves_contradictory_caps()
    recs = edited.get("records") or []
    if len(recs) != S.N:
        return fail(f"expected {S.N} dispatch records, got {len(recs)}")

    first_text = recs[0]["dispatch_spec_text"]
    last_text = recs[-1]["dispatch_spec_text"]
    h_first, pid_first = hash_text_via_child(first_text)
    h_last, pid_last = hash_text_via_child(last_text)
    reviewer_pid = os.getpid()

    named = edited.get("named_hashes") or {}
    drifted = edited.get("drifted_units") or []
    kinds = {d.get("kind") for d in drifted}

    with tempfile.TemporaryDirectory(prefix="tst0163-p2b-") as td:
        live = Path(td) / "live.json"
        live.write_text(last_text, encoding="utf-8")
        live_hash, live_pid = independent_digest(live)

    ok = (
        edited["result"] == "CONTRACT-DRIFT"
        and kinds == {"CONTRACT-DRIFT"}
        and h_first == named.get("dispatch") == edited["h_before"]
        and h_last == named.get("fanin") == edited["h_after"] == live_hash
        and h_first != h_last
        and pid_first != reviewer_pid
        and pid_last != reviewer_pid
        and live_pid != reviewer_pid
        and naive["pass"] is True
        and naive.get("mutant_misses") is True
        and json.loads(first_text)["tool_call_cap"] == S.CAP_BEFORE
        and json.loads(last_text)["tool_call_cap"] == S.CAP_AFTER
    )
    payload = {
        "probe": "probe2-independent-hash",
        "unit_id": UNIT,
        "pass": ok,
        "reviewer_pid": reviewer_pid,
        "hasher_pids": [pid_first, pid_last, live_pid],
        "h_first": h_first,
        "h_last": h_last,
        "live_hash": live_hash,
        "named_hashes": named,
        "kinds": sorted(kinds),
        "n_drifted": edited.get("n_drifted"),
        "caps_observed": edited.get("caps_observed"),
        "naive_mutant_misses": naive.get("mutant_misses"),
        "naive_silent_on_good": naive.get("silent_on_good"),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"named_dispatch={named.get('dispatch')} named_fanin={named.get('fanin')} "
        f"child_first={h_first} child_last={h_last} live={live_hash} "
        f"naive_misses={naive.get('mutant_misses')}"
    )
    if edited["result"] != "CONTRACT-DRIFT":
        return fail("edited detect run was not CONTRACT-DRIFT")
    if kinds != {"CONTRACT-DRIFT"}:
        return fail(f"drift kind {kinds}")
    if h_first != named.get("dispatch"):
        return fail("independent hash of dispatch-spec bytes != named dispatch hash")
    if h_last != named.get("fanin"):
        return fail("independent hash of post-edit spec != named fan-in hash")
    if h_first == h_last:
        return fail("independently recomputed hashes were equal")
    if not naive["pass"] or not naive.get("mutant_misses"):
        return fail("last-write-wins mutant did not leave contradictory caps live")
    if pid_first == reviewer_pid or live_pid == reviewer_pid:
        return fail("hasher pid was not a separate process")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    row = tests.get("test_naive_last_write_wins_leaves_contradictory_caps")
    if not row or row.get("result") != "PASS":
        return fail("receipt missing PASS for naive last-write-wins control")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("receipt reviewer")
    evidence = doc.get("evidence") or []
    if len(evidence) < 2:
        return fail("receipt evidence < 2 independent signals")

    print(
        "SUCCESS:TST-0163-probe2 independent hashes match named CONTRACT-DRIFT; "
        "naive last-write-wins misses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
