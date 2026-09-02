#!/usr/bin/env python3
"""Probe 2: reviewer kill point + truncated-journal refuse + append-only prefix.

Independent of probe 1's implementer sweep. Uses a kill point the implementer
list does not enumerate, then a mid-record truncate that must refuse rather
than guess. Prefix sha256 of earlier bytes must be unchanged after a later
append.
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
    recover_on_launch,
    run_kill_trial,
    seed_old_dest,
    seed_payload,
)

ART = REPO / "command-center/receipts/IMP-0028.json"
JOURNAL_SRC = PLUGIN / "txn_journal.py"


def _receipt_ok() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"self-declared {doc.get('state')}"
    if "SUCCESS:IMP-0028" not in text:
        return "sentinel absent"
    return None


def seed_payload_v3(root: Path) -> Path:
    payload = Path(root) / "payload-v3"
    (payload / "rules").mkdir(parents=True, exist_ok=True)
    (payload / "plugin.json").write_text(
        '{"name":"txn-demo","version":"3.0.0"}\n', encoding="utf-8"
    )
    (payload / "rules" / "a.md").write_text("newer-rules\n", encoding="utf-8")
    (payload / "skills").mkdir(parents=True, exist_ok=True)
    (payload / "skills" / "x.md").write_text("skill-v3\n", encoding="utf-8")
    return payload


def main() -> int:
    err = _receipt_ok()
    if err:
        print(f"FAILED:IMP-0028-probe2 {err}")
        return 1

    if REVIEWER_KILL_POINT in IMPLEMENTER_KILL_POINTS:
        print("FAILED:IMP-0028-probe2 reviewer kill point was implementer-enumerated")
        return 1

    src = JOURNAL_SRC.read_text(encoding="utf-8")
    if "O_APPEND" not in src or "os.O_TRUNC" in src:
        print("FAILED:IMP-0028-probe2 journal source is not append-only")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0028-p2-") as td:
        root = Path(td)
        rev = run_kill_trial(REVIEWER_KILL_POINT, work=root / "rev")
        work = root / "trunc"
        work.mkdir()
        dest = work / "dest"
        payload = seed_payload(work)
        seed_old_dest(dest)
        journal_path = work / "dest.txn.jsonl"
        JournaledInstall(dest, payload, journal_path).run()
        before = journal_path.read_bytes()
        n, sha = TxnJournal(journal_path).prefix_fingerprint(len(before))
        payload2 = seed_payload_v3(work)
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
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(JOURNAL_SRC),
                "recover",
                "--journal",
                str(trunc_path),
                "--dest",
                str(dest),
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    reviewer_ok = (
        rev["kill_landed"] is True
        and rev["legal_state"] in {LEGAL_OLD, LEGAL_NEW}
        and rev["valid"] is True
        and rev["live"]["staging_exists"] is False
        and rev["live"]["old_exists"] is False
        and rev["legal_state"] == rev["recover"].get("claimed_legal_state")
    )
    truncate_ok = (
        refused
        and not truncated.endswith(b"\n")
        and proc.returncode == 3
        and "REFUSED" in (proc.stderr or "")
    )
    report = {
        "probe": "probe2-reviewer-truncate",
        "unit_id": "IMP-0028",
        "reviewer_kill_point": REVIEWER_KILL_POINT,
        "reviewer_not_in_implementer_list": REVIEWER_KILL_POINT
        not in IMPLEMENTER_KILL_POINTS,
        "reviewer_kill_landed": rev["kill_landed"],
        "reviewer_legal_state": rev["legal_state"],
        "reviewer_claimed": rev["recover"].get("claimed_legal_state"),
        "reviewer_action": rev["recover"].get("action"),
        "reviewer_live_digest": rev["live_digest"],
        "reviewer_ok": reviewer_ok,
        "truncate_refused": refused,
        "truncate_message": refuse_msg,
        "truncate_cli_rc": proc.returncode,
        "truncate_ok": truncate_ok,
        "append_only_prefix_unchanged": prefix_ok,
        "source_uses_o_append": "O_APPEND" in src,
        "pass": reviewer_ok and truncate_ok and prefix_ok,
    }
    print(json.dumps(report, sort_keys=True))
    if not reviewer_ok:
        print("FAILED:IMP-0028-probe2 reviewer kill point did not reach a legal state")
        return 1
    if not truncate_ok:
        print("FAILED:IMP-0028-probe2 truncated journal was not refused")
        return 1
    if not prefix_ok:
        print("FAILED:IMP-0028-probe2 journal prefix mutated (not append-only)")
        return 1
    print(
        "SUCCESS:IMP-0028-probe2 reviewer kill + truncate refuse + append-only prefix"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
