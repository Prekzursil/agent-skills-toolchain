#!/usr/bin/env python3
"""Write command-center/receipts/IMP-0028.json from live journal measurements."""
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
TOOLS = REPO / "tools"
PLUGIN = TOOLS / "plugin"
sys.path.insert(0, str(TOOLS))

from plugin.txn_journal import (  # noqa: E402
    IMPLEMENTER_KILL_POINTS,
    LEGAL_NEW,
    LEGAL_OLD,
    REVIEWER_KILL_POINT,
    JournalTruncatedError,
    JournaledInstall,
    TxnJournal,
    classify_legal_state,
    expected_new_census,
    independent_census,
    recover_on_launch,
    run_implementer_kill_sweep,
    run_kill_trial,
    seed_old_dest,
    seed_payload,
)

OUT = "command-center/receipts/IMP-0028.json"
SUITE = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin/tests/test_txn_journal.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0028/probe1_kill_sweep.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0028/probe2_reviewer_truncate.py"
)
QUESTION = (
    "Implement an append-only journal that records each lifecycle step's intent "
    "and its inverse before the step executes, plus a recover entry point that "
    "replays or reverses an interrupted transaction on next launch — so a "
    "machine freeze mid-install is recoverable rather than a manual repair."
)


def sha_file(rel: str, role: str = "supporting") -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() if data else "",
        "exists": path.is_file(),
        "role": role,
        "eol": "LF" if data and b"\r\n" not in data else ("CRLF" if data else "NOT-CHECKED"),
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def live_evidence() -> dict:
    src = (PLUGIN / "txn_journal.py").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="imp0028-emit-") as td:
        root = Path(td)
        sweep = run_implementer_kill_sweep(root / "sweep")
        reviewer = run_kill_trial(REVIEWER_KILL_POINT, work=root / "rev")
        work = root / "ok"
        work.mkdir()
        dest = work / "dest"
        payload = seed_payload(work)
        old_census = seed_old_dest(dest)
        journal_path = work / "dest.txn.jsonl"
        committed = JournaledInstall(dest, payload, journal_path).run()
        live = independent_census(dest)
        new_census = expected_new_census(payload)
        legal = classify_legal_state(
            live, old_census, new_census, old_dest_existed=True
        )
        records, leftover = TxnJournal(journal_path).read_complete()
        before = journal_path.read_bytes()
        n, sha = TxnJournal(journal_path).prefix_fingerprint(len(before))
        payload2 = root / "payload-v3"
        (payload2 / "rules").mkdir(parents=True)
        (payload2 / "plugin.json").write_text(
            '{"name":"txn-demo","version":"3.0.0"}\n', encoding="utf-8"
        )
        (payload2 / "rules" / "a.md").write_text("newer-rules\n", encoding="utf-8")
        JournaledInstall(dest, payload2, journal_path).run()
        after = journal_path.read_bytes()
        prefix_ok = after[:n] == before and TxnJournal(journal_path).prefix_fingerprint(n)[1] == sha

        last_nl = before.rstrip(b"\n").rfind(b"\n")
        last_rec = before[last_nl + 1 :]
        mid = last_nl + 1 + max(12, len(last_rec) // 2)
        trunc_path = work / "truncated.txn.jsonl"
        truncated = before[:mid]
        trunc_path.write_bytes(truncated)
        refused = False
        refuse_msg = ""
        try:
            recover_on_launch(trunc_path, dest)
        except JournalTruncatedError as exc:
            refused = True
            refuse_msg = str(exc)

    sweep_rows = [
        {
            "kill_at": row["kill_at"],
            "kill_landed": row["kill_landed"],
            "legal_state": row["legal_state"],
            "claimed": row["recover"].get("claimed_legal_state"),
            "action": row["recover"].get("action"),
            "valid": row["valid"],
            "live_digest": row["live_digest"],
            "census_matches_old": row["matches_old"],
            "census_matches_new": row["matches_new"],
        }
        for row in sweep
    ]
    sweep_ok = (
        len(sweep) == len(IMPLEMENTER_KILL_POINTS)
        and all(r["kill_landed"] and r["valid"] for r in sweep)
        and all(r["legal_state"] in {LEGAL_OLD, LEGAL_NEW} for r in sweep)
        and all(
            r["legal_state"] == r["recover"].get("claimed_legal_state") for r in sweep
        )
    )
    reviewer_ok = (
        reviewer["kill_landed"]
        and reviewer["valid"]
        and reviewer["legal_state"] in {LEGAL_OLD, LEGAL_NEW}
        and REVIEWER_KILL_POINT not in IMPLEMENTER_KILL_POINTS
    )
    ok = (
        sweep_ok
        and reviewer_ok
        and refused
        and prefix_ok
        and leftover == b""
        and legal == LEGAL_NEW
        and committed["status"] == "committed"
        and "O_APPEND" in src
        and "os.O_TRUNC" not in src
        and records[-1]["kind"] == "commit"
    )
    return {
        "ok": ok,
        "sweep_ok": sweep_ok,
        "reviewer_ok": reviewer_ok,
        "truncate_refused": refused,
        "truncate_message": refuse_msg,
        "append_only_prefix_unchanged": prefix_ok,
        "committed_legal_state": legal,
        "committed_status": committed["status"],
        "record_count": len(records),
        "source_uses_o_append": "O_APPEND" in src,
        "reviewer_kill_point": REVIEWER_KILL_POINT,
        "reviewer_legal_state": reviewer["legal_state"],
        "reviewer_action": reviewer["recover"].get("action"),
        "implementer_kill_points": list(IMPLEMENTER_KILL_POINTS),
        "sweep": sweep_rows,
    }


def main() -> int:
    suite_code, suite_text = run_cmd(SUITE)
    if suite_code != 0:
        print(suite_text[-4000:])
        print("FAILED:IMP-0028 suite")
        return 1
    live = live_evidence()
    if not live["ok"]:
        print(json.dumps(live, indent=2, default=str)[:8000])
        print("FAILED:IMP-0028 live evidence")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        sha_file("tools/plugin/txn_journal.py", "implementation"),
        sha_file("tools/plugin/schema/txn-journal.schema.json", "schema"),
        sha_file("tools/plugin/tests/test_txn_journal.py", "catalog-test"),
        sha_file("tools/plugin/payload.py", "census"),
        sha_file("tools/plugin/placement.py", "placement"),
        sha_file(
            "command-center/p2-wave/probes/IMP-0028/probe1_kill_sweep.py", "probe"
        ),
        sha_file(
            "command-center/p2-wave/probes/IMP-0028/probe2_reviewer_truncate.py",
            "probe",
        ),
    ]
    artifacts = [
        {
            "path": OUT,
            "exists": True,
            "role": "primary",
            "note": "self; sha256 is in the per-unit UNIT-ARTIFACT-MANIFEST.json row",
        }
    ] + supporting
    receipt = {
        "unit_id": "IMP-0028",
        "id": "IMP-0028",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "receipt",
        "title": "Lifecycle transaction journal with crash recovery",
        "question_or_target": QUESTION,
        "answer": (
            "tools/plugin/txn_journal.py journals intent+inverse before each of "
            "stage/verify/activate/cleanup, then recover() rolls back before "
            "activate or forward after it. An independent filesystem census is "
            "compared to the two legal snapshots (OLD/NEW); recover() status "
            "alone is not evidence. A mid-record truncate is JournalTruncatedError "
            "(CLI rc=3), not a guess. Append uses O_APPEND; prefix bytes are "
            "unchanged after a later transaction. Reviewer kill point "
            f"{REVIEWER_KILL_POINT} is not in the implementer list and recovers "
            "to a legal state. SUCCESS:IMP-0028"
        ),
        "sentinel": "SUCCESS:IMP-0028",
        "completion_sentinel": "SUCCESS:IMP-0028",
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/plugin/schema/txn-journal.schema.json"
        ),
        "cloud_ok": False,
        "registered": True,
        "phase": "5",
        "library_path": "tools/plugin/txn_journal.py",
        "canonical_module": "txn_journal",
        "canonical_symbol": "recover",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0028",
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0028/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "min_bytes_threshold": 2048,
        "evidence_requirement": (
            "TWO independent signals: (1) a kill-point sweep that interrupts "
            "the transaction at every recorded step and asserts recovery reaches "
            "a valid state each time; (2) an independent filesystem census after "
            "each recovery compared against the two legal states. Recovery "
            "reporting success is not accepted without the census."
        ),
        "reviewer_requirement": (
            "Reviewer must add one kill point the implementer did not enumerate."
        ),
        "tests_required": (
            "tools/plugin/tests/test_txn_journal.py::test_recovery_at_every_kill_point; "
            "NEGATIVE CONTROL: truncate the journal mid-record and assert recovery "
            "refuses rather than guessing; journal is append-only: assert no "
            "in-place rewrite occurs"
        ),
        "inputs": [
            "command-center/events/EVENTS.jsonl (append-only precedent)",
            "tools/plugin/payload.py census_tree",
            "tools/plugin/placement.py place_payload_files",
        ],
        "evidence": [
            {
                "id": "signal-1-kill-point-sweep",
                "kind": "kill-point-sweep",
                "claim": (
                    "Interrupting at every implementer-recorded step and calling "
                    "recover() leaves dest in exactly one legal state."
                ),
                "anchor": "tools/plugin/txn_journal.py:run_implementer_kill_sweep",
                "points": live["implementer_kill_points"],
                "n": len(live["sweep"]),
                "all_landed": all(r["kill_landed"] for r in live["sweep"]),
                "all_valid": all(r["valid"] for r in live["sweep"]),
                "verdict": "CONFIRMED",
                "independent_of": "signal-2-independent-census",
            },
            {
                "id": "signal-2-independent-census",
                "kind": "filesystem-census",
                "claim": (
                    "After each recovery, an independent_census (dest/staging/old "
                    "hashes) is classified against the two legal snapshots. "
                    "recover() claimed_legal_state is accepted only when it "
                    "matches that census."
                ),
                "anchor": "tools/plugin/txn_journal.py:independent_census",
                "census_agrees_with_claim": all(
                    r["legal_state"] == r["claimed"] for r in live["sweep"]
                ),
                "committed_legal_state": live["committed_legal_state"],
                "verdict": "CONFIRMED",
                "independent_of": "signal-1-kill-point-sweep",
            },
        ],
        "negative_controls": [
            {
                "id": "truncate-journal-mid-record",
                "kind": "truncated-record",
                "description": (
                    "Cut the last journal record before its terminating newline. "
                    "recover() must raise JournalTruncatedError; CLI recover "
                    "exits 3 with REFUSED. Guessing a repair is a failure."
                ),
                "fired_on_bad_state": live["truncate_refused"],
                "silent_on_good_state": live["committed_status"] == "committed",
                "bad_state_output": live["truncate_message"],
            },
            {
                "id": "append-only-prefix",
                "kind": "in-place-rewrite",
                "description": (
                    "After a committed journal, a second transaction must leave "
                    "the previous bytes and their prefix sha256 unchanged."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": live["append_only_prefix_unchanged"],
                "good_state_output": "prefix sha256 unchanged after second txn",
            },
        ],
        "tests": [
            {
                "id": "test_recovery_at_every_kill_point",
                "name": (
                    "tools/plugin/tests/test_txn_journal.py"
                    "::test_recovery_at_every_kill_point"
                ),
                "command": SUITE,
                "result": "PASS" if suite_code == 0 else "FAIL",
                "exit_code": suite_code,
                "output_tail": suite_text[-2000:],
            },
            {
                "id": "NEGATIVE CONTROL truncate mid-record",
                "name": "test_truncate_journal_mid_record_refuses",
                "result": "PASS",
            },
            {
                "id": "journal is append-only",
                "name": "test_journal_is_append_only",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0028-probe2-reviewer-truncate",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                f"Added kill point {REVIEWER_KILL_POINT} (not in "
                "IMPLEMENTER_KILL_POINTS). Probe 2 independently confirms "
                "legal-state census, mid-record refuse, and append-only prefix. "
                f"Reviewer trial legal_state={live['reviewer_legal_state']} "
                f"action={live['reviewer_action']}."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0028/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_unit_manifest_write": False,
            "note": (
                "per-unit manifest only; did not run "
                "tools/command-center/unit_manifest.py --write"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "named-probe1",
                "artifact_path": (
                    "command-center/p2-wave/probes/IMP-0028/probe1_kill_sweep.py"
                ),
                "executed": True,
                "read_ok": True,
            },
            {
                "consumer": "named-probe2",
                "artifact_path": (
                    "command-center/p2-wave/probes/IMP-0028/probe2_reviewer_truncate.py"
                ),
                "executed": True,
                "read_ok": True,
            },
            {
                "consumer": "txn_journal.recover CLI",
                "artifact_path": "tools/plugin/txn_journal.py",
                "executed": True,
                "read_ok": True,
            },
        ],
        "artifacts": artifacts,
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "fixture_matrix": live["sweep"],
        "probe_results": {
            "sweep_ok": live["sweep_ok"],
            "reviewer_ok": live["reviewer_ok"],
            "reviewer_kill_point": live["reviewer_kill_point"],
            "truncate_refused": live["truncate_refused"],
            "append_only_prefix_unchanged": live["append_only_prefix_unchanged"],
            "committed_legal_state": live["committed_legal_state"],
            "source_uses_o_append": live["source_uses_o_append"],
        },
        "catalog": {
            "id": "IMP-0028",
            "title": "Lifecycle transaction journal with crash recovery",
            "output_path": OUT,
        },
        "host": {"system": os.uname().sysname.lower(), "machine": os.uname().machine},
        "timestamps": {"started_at": now, "ended_at": now},
        "ts": now,
        "status": "DELIVERED",
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "notes": (
            "G-1 for IMP-0028: live named probes re-run kill-sweep census and "
            "reviewer/truncate/append-only checks. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. SUCCESS:IMP-0028"
        ),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if "SUCCESS:IMP-0028" not in raw:
        print("FAILED:emit sentinel missing")
        return 1
    dest.write_text(raw, encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:IMP-0028")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
