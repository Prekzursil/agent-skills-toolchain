#!/usr/bin/env python3
"""Named probe 2: live catalogue signal + schema both-states + matrix honesty.

Mechanically different from probe 1 (command/uname). Reads CI workflows, ssh
Host entries, hypervisor CLIs, and CI env; does not use uname as the oracle.
Also re-validates the artifact against impossibility-record.schema.json and
proves the schema rejects one-signal / no-settling / garbage / supported-row.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import estate as E  # noqa: E402
import matrix as M  # noqa: E402
import schema_ctl as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0098-macos-reachability.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0098-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0098":
        print("FAILED:CNF-0098-probe2 unit_id", doc.get("unit_id"))
        return 1

    proofs = doc.get("two_signal_proof") or []
    methods = [p.get("method") for p in proofs if isinstance(p, dict)]
    if len(proofs) < 2:
        print("FAILED:CNF-0098-probe2 fewer than two signals")
        return 1
    if len(set(methods)) < 2:
        print("FAILED:CNF-0098-probe2 signals are not mechanically different")
        return 1

    live = E.signal_catalogue(REPO)
    cat = next((p for p in proofs if p.get("method") == "file-read"), None)
    if cat is None:
        print("FAILED:CNF-0098-probe2 no file-read catalogue signal")
        return 1
    if cat.get("fingerprint") != live["fingerprint"]:
        print("FAILED:CNF-0098-probe2 catalogue fingerprint drift")
        print("live", live["fingerprint"], live["observation"])
        print("art ", cat.get("fingerprint"), cat.get("observation"))
        return 1

    rows = doc.get("matrix_rows") or []
    try:
        M.assert_honest(rows)
    except AssertionError as exc:
        print("FAILED:CNF-0098-probe2 dishonest matrix", exc)
        return 1
    macos_rows = [r for r in rows if r.get("os") == "macos"]
    if not macos_rows:
        print("FAILED:CNF-0098-probe2 no macos matrix row")
        return 1
    for r in rows:
        if r.get("evidence_state") == "supported" or r.get("amended_tier") == "supported":
            print("FAILED:CNF-0098-probe2 supported without a run", r.get("id"))
            return 1
        if r.get("evidence_state") not in M.ALLOWED:
            print("FAILED:CNF-0098-probe2 bad evidence_state", r)
            return 1
    if not doc.get("macos_reachable"):
        for r in macos_rows:
            if r.get("evidence_state") != "untested":
                print("FAILED:CNF-0098-probe2 unreachable macos not untested", r)
                return 1

    try:
        S.assert_valid(doc)
        ctl = S.both_states(doc)
    except AssertionError as exc:
        print("FAILED:CNF-0098-probe2 schema control", exc)
        return 1

    out = {
        "probe": "probe2-runner-inventory",
        "unit_id": "CNF-0098",
        "method": "file-read",
        "macos_runner_present": live["macos_runner_present"],
        "fingerprint": live["fingerprint"],
        "observation": live["observation"],
        "macos_rows": len(macos_rows),
        "supported_without_run": 0,
        "schema_controls": ctl,
        "matches_artifact": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"catalogue_macos={live['macos_runner_present']} "
        f"macos_rows={len(macos_rows)} "
        f"one_signal_rejected={ctl['one_signal_rejected']} "
        f"garbage_rejected={ctl['garbage_rejected']}"
    )
    print("SUCCESS:CNF-0098-probe2 runner catalogue schema matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
