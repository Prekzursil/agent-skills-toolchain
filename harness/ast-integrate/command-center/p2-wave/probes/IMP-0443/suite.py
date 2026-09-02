#!/usr/bin/env python3
"""Live kill-and-resume, idempotent replay, torn-line, and mutation suite."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))
from run_ledger import (  # noqa: E402
    RunLedger,
    append_record,
    duplicate_ids,
    executed_multiset,
    read_records,
    split_complete_lines,
)

RUNNER = HERE / "runner.py"
CATALOG_PATH = HERE / "fixtures" / "catalog.json"
PY = sys.executable


def load_catalog() -> list[str]:
    doc = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [str(u) for u in doc["units"]]


def percent_n(size: int, percent: int) -> int:
    n = int(round(size * percent / 100.0))
    return min(size - 1, max(1, n))


def snapshot(ledger_path: Path) -> dict[str, Any]:
    recs = read_records(ledger_path) if ledger_path.is_file() else []
    multi = executed_multiset(recs)
    completed = [
        str(r["unit_id"]) for r in recs if r.get("kind") == "completed"
    ]
    first: list[str] = []
    seen: set[str] = set()
    for uid in completed:
        if uid not in seen:
            seen.add(uid)
            first.append(uid)
    return {
        "record_count": len(recs),
        "completed": first,
        "completed_count": len(first),
        "executed_multiset": multi,
        "duplicates": duplicate_ids(multi),
    }


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _popen(args: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        args,
        cwd=str(REPO),
        env=_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _run(args: list[str], timeout: float = 20.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(REPO),
        env=_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )


def runner_cmd(cat: Path, ledger: Path, extra: list[str] | None = None) -> list[str]:
    cmd = [
        PY,
        "-B",
        str(RUNNER),
        "--catalog",
        str(cat),
        "--ledger",
        str(ledger),
    ]
    if extra:
        cmd.extend(extra)
    return cmd


def kill_and_resume(catalog: list[str], kill_percent: int) -> dict[str, Any]:
    n = percent_n(len(catalog), kill_percent)
    tmp = Path(tempfile.mkdtemp(prefix=f"imp0443-k{kill_percent}-"))
    try:
        ledger = tmp / "run.jsonl"
        cat = tmp / "catalog.json"
        hold = tmp / "go"
        cat.write_text(json.dumps({"units": catalog}) + "\n", encoding="utf-8")
        child = _popen(
            runner_cmd(
                cat,
                ledger,
                [
                    "--delay-ms",
                    "5",
                    "--hold-file",
                    str(hold),
                    "--stall-after",
                    str(n),
                    "--run-id",
                    f"kill-{kill_percent}",
                ],
            )
        )
        hold.write_text("go\n", encoding="utf-8")
        deadline = time.time() + 15.0
        while time.time() < deadline:
            if snapshot(ledger)["completed_count"] >= n:
                break
            if child.poll() is not None:
                break
            time.sleep(0.005)
        if child.poll() is None:
            child.send_signal(signal.SIGKILL)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        else:
            child.wait(timeout=5)
        before = snapshot(ledger)
        before["child_returncode"] = child.returncode
        resume = _run(
            runner_cmd(cat, ledger, ["--delay-ms", "0", "--run-id", f"resume-{kill_percent}"])
        )
        after = snapshot(ledger)
        after["resume_returncode"] = resume.returncode
        after["resume_stderr"] = (resume.stderr or "")[-400:]
        after_set = set(after["executed_multiset"])
        catalog_set = set(catalog)
        coverage = after_set == catalog_set
        counts_ok = all(v == 1 for v in after["executed_multiset"].values())
        killed = before["child_returncode"] not in (0, None)
        return {
            "id": f"kill-at-{kill_percent}",
            "kill_percent": kill_percent,
            "kill_n": n,
            "kill_signal": "SIGKILL",
            "completed_before_resume": before["completed"],
            "executed_multiset_before": before["executed_multiset"],
            "executed_multiset_after": after["executed_multiset"],
            "duplicates": after["duplicates"],
            "catalog_coverage_after": bool(coverage and counts_ok),
            "before": before,
            "after": after,
            "records": read_records(ledger),
            "ok": (
                before["completed_count"] == n
                and killed
                and resume.returncode == 0
                and coverage
                and counts_ok
                and not after["duplicates"]
            ),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def idempotent_replay(catalog: list[str]) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="imp0443-replay-"))
    try:
        ledger = tmp / "run.jsonl"
        cat = tmp / "catalog.json"
        cat.write_text(json.dumps({"units": catalog}) + "\n", encoding="utf-8")
        args = runner_cmd(cat, ledger)
        first = _run(args)
        snap1 = snapshot(ledger)
        n1 = snap1["record_count"]
        second = _run(args)
        snap2 = snapshot(ledger)
        third = _run(args)
        snap3 = snapshot(ledger)
        inproc = RunLedger(ledger, run_id="inproc-replay")
        pending_after = inproc.pending(catalog)
        noop = inproc.record_completed(catalog[0])
        snap4 = snapshot(ledger)
        expected = {u: 1 for u in catalog}
        ok = (
            first.returncode == 0
            and second.returncode == 0
            and third.returncode == 0
            and snap1["executed_multiset"] == expected
            and snap2["record_count"] == n1
            and snap3["record_count"] == n1
            and snap4["record_count"] == n1
            and not snap3["duplicates"]
            and pending_after == []
            and noop is None
        )
        return {
            "id": "idempotent-replay",
            "ok": ok,
            "first_returncode": first.returncode,
            "records_after_first": n1,
            "records_after_second": snap2["record_count"],
            "records_after_third": snap3["record_count"],
            "executed_multiset": snap3["executed_multiset"],
            "duplicates": snap3["duplicates"],
            "pending_after": pending_after,
            "inproc_second_complete_was_noop": noop is None,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def mutation_non_idempotent(catalog: list[str]) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="imp0443-mutant-"))
    try:
        ledger = tmp / "run.jsonl"
        cat = tmp / "catalog.json"
        cat.write_text(json.dumps({"units": catalog}) + "\n", encoding="utf-8")
        good = _run(runner_cmd(cat, ledger))
        good_snap = snapshot(ledger)
        mutant = _run(runner_cmd(cat, ledger, ["--mutant"]))
        bad = snapshot(ledger)
        produced = bool(bad["duplicates"]) and any(
            n > 1 for n in bad["executed_multiset"].values()
        )
        replay_would_pass = (
            not good_snap["duplicates"]
            and good_snap["executed_multiset"] == {u: 1 for u in catalog}
        )
        turned_red = produced and replay_would_pass
        return {
            "id": "skip-completed-check",
            "ok": turned_red and good.returncode == 0 and mutant.returncode == 0,
            "produced_duplicates": produced,
            "turned_test_red": turned_red,
            "duplicate_unit_ids": bad["duplicates"],
            "good_multiset": good_snap["executed_multiset"],
            "mutant_multiset": bad["executed_multiset"],
            "good_returncode": good.returncode,
            "mutant_returncode": mutant.returncode,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def torn_last_line() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="imp0443-torn-"))
    try:
        path = tmp / "run.jsonl"
        append_record(
            path,
            {
                "seq": 1,
                "kind": "completed",
                "unit_id": "IMP0443-TORN-KEEP",
                "run_id": "torn",
                "ts": "2026-08-24T00:00:00.000000Z",
            },
        )
        with path.open("ab") as fh:
            fh.write(b'{"seq":2,"kind":"completed","unit_id":"IMP0443-TORN-DROP"')
            fh.flush()
            os.fsync(fh.fileno())
        raw = path.read_bytes()
        bodies, incomplete = split_complete_lines(raw)
        loaded = read_records(path)
        ids = [r["unit_id"] for r in loaded]
        ok = (
            incomplete is not None
            and b"IMP0443-TORN-DROP" in incomplete
            and ids == ["IMP0443-TORN-KEEP"]
            and len(bodies) == 1
        )
        return {
            "id": "torn-last-line-absent",
            "ok": ok,
            "kept": ids,
            "incomplete_present": incomplete is not None,
            "dropped_marker_only_in_tail": bool(
                incomplete and b"IMP0443-TORN-DROP" in incomplete
            ),
            "complete_line_count": len(bodies),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_suite() -> dict[str, Any]:
    catalog = load_catalog()
    traces = [kill_and_resume(catalog, p) for p in (10, 50, 60, 90)]
    replay = idempotent_replay(catalog)
    mutant = mutation_non_idempotent(catalog)
    torn = torn_last_line()
    kill60 = next(t for t in traces if t["kill_percent"] == 60)
    all_kills_ok = all(t["ok"] for t in traces)
    return {
        "ok": all_kills_ok and replay["ok"] and mutant["ok"] and torn["ok"],
        "catalog": catalog,
        "traces": traces,
        "replay": replay,
        "mutation": mutant,
        "torn": torn,
        "kill60": kill60,
        "all_kills_ok": all_kills_ok,
    }


def main() -> int:
    report = run_suite()
    summary = {
        "ok": report["ok"],
        "kills": [
            {
                "id": t["id"],
                "ok": t["ok"],
                "before": t["before"]["completed_count"],
                "after_n": len(t["executed_multiset_after"]),
                "duplicates": t["duplicates"],
                "coverage": t["catalog_coverage_after"],
            }
            for t in report["traces"]
        ],
        "replay_ok": report["replay"]["ok"],
        "mutation_produced_duplicates": report["mutation"]["produced_duplicates"],
        "torn_ok": report["torn"]["ok"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not report["ok"]:
        print("FAILED:IMP-0443 suite")
        for t in report["traces"]:
            if not t["ok"]:
                print(
                    f"  {t['id']} before={t['before']['completed_count']} "
                    f"rc={t['before'].get('child_returncode')} "
                    f"resume_rc={t['after'].get('resume_returncode')} "
                    f"dups={t['duplicates']} coverage={t['catalog_coverage_after']}"
                )
        if not report["replay"]["ok"]:
            print(f"  replay={report['replay']}")
        if not report["mutation"]["ok"]:
            print(f"  mutation={report['mutation']}")
        if not report["torn"]["ok"]:
            print(f"  torn={report['torn']}")
        return 1
    print("SUCCESS:IMP-0443-suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
