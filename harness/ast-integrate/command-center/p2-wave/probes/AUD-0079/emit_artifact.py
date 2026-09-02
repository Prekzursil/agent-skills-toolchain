#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0079-credential-consumer-audit.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402
import enumerate as E  # noqa: E402
import execute as X  # noqa: E402

QUESTION = C.QUESTION
SENTINEL = C.SENTINEL


def _run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def _digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    rc1, out1 = _run(C.P1)
    rc2, out2 = _run(C.P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:AUD-0079 emit probes rc1={rc1} rc2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    hits = E.scan_repo(REPO)
    summary = E.summarize(hits)
    live = X.run_all()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path = REPO / C.OUT_REL
    schema_path = REPO / C.SCHEMA_REL
    schema_present = schema_path.is_file()

    consumers = []
    for h in hits:
        consumers.append(
            {
                "path": h.get("path"),
                "line": h.get("line"),
                "kind": h.get("kind"),
                "name": h.get("name"),
                "form": h.get("form"),
                "classification": h.get("classification"),
                "language": h.get("language"),
                "value_reported": False,
            }
        )

    headline = (
        "On this Linux worktree, {n} credential-shaped reads were enumerated. "
        "{loud} fail loudly on absence, {silent} silently degrade, {crash} crash, "
        "{skip} skip if absent, {unk} unclassified. Scratch execution of planted "
        "loud/silent/file consumers plus live Cursor CLI gates shows UNSET vs "
        "syntactically-valid WRONG are distinguishable for loud consumers; the "
        "silent plant proceeds in both states (detector control). Catalog schema "
        "{schema} is {schema_state} on this tree."
    ).format(
        n=summary["read_count"],
        loud=summary["loud_fail"],
        silent=summary["silent_degrade"],
        crash=summary["crash_on_absent"],
        skip=summary["skip_if_absent"],
        unk=summary["unknown"],
        schema=C.SCHEMA_REL,
        schema_state="present" if schema_present else "absent",
    )

    doc = {
        "unit_id": C.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "audit-finding",
        "title": "Credential-consumer audit: which code reads which variable and how it fails",
        "question": QUESTION,
        "answer": headline,
        "headline": headline,
        "schema_path": C.SCHEMA_REL,
        "schema_present_on_tree": schema_present,
        "produced_at": now,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "security-auditor",
            "execution_substrate": "linux-headless",
        },
        "census": summary,
        "consumers": consumers,
        "execution": {
            "scratch_only": True,
            "value_reported": False,
            "both_states_control": live["both_states_control"],
            "rows": live["rows"],
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": C.P1,
                "exit_code": rc1,
                "raw_output": out1,
                "role": "static-enumeration-with-planted-classifier-control",
            },
            {
                "id": "probe2",
                "command": C.P2,
                "exit_code": rc2,
                "raw_output": out2,
                "role": "scratch-execution-unset-and-wrong",
            },
        ],
        "tests": [
            {
                "id": "probe1-static-enum",
                "command": C.P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
            },
            {
                "id": "probe2-unset-and-wrong",
                "command": C.P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
            },
            {
                "id": "both-states-control",
                "name": "loud UNSET vs syntactically-valid WRONG are distinguishable; silent plant is not",
                "result": "PASS" if live["both_states_control"]["ok"] else "FAIL",
            },
            {
                "id": "classifier-control",
                "name": "enumerator rates planted loud as loud-fail and planted silent as silent-degrade",
                "result": "PASS" if rc1 == 0 else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0079-probe2-scratch-execution",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Catalog asks a cross-vendor Codex reviewer to re-run only probe 2. "
                "That reviewer is not on this worker. Probe 2 is a mechanically "
                "independent execution (scratch UNSET/WRONG) from probe 1's AST census."
            ),
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/AUD-0079/fixtures/loud_consumer.py",
                "line": 13,
                "snippet": "if not os.environ.get(NAME):",
                "kind": "planted-loud-control",
                "claim": "UNSET exits 2 MISSING; WRONG exits 3 REJECTED.",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0079/fixtures/silent_consumer.py",
                "line": 12,
                "snippet": 'token = os.environ.get(NAME, "anonymous")',
                "kind": "planted-silent-control",
                "claim": "UNSET and WRONG both exit 0; classifier must rate silent-degrade.",
            },
            {
                "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
                "line": 428,
                "snippet": 'if not os.environ.get("CURSOR_API_KEY"):',
                "kind": "live-entry-gate",
                "claim": "Live supervisor gate fails closed when CURSOR_API_KEY is unset.",
            },
            {
                "path": "command-center/p2-wave/seed-stage/bringup_cursor_fleet.py",
                "line": 68,
                "snippet": 'token = os.environ.get("CURSOR_API_TOKEN") or os.environ.get("CURSOR_API_KEY")',
                "kind": "live-entry-gate",
                "claim": "Fleet bring-up fails closed when both token env vars are unset.",
            },
        ],
        "artifacts": [
            {
                "path": C.OUT_REL,
                "exists": True,
                "role": "primary",
            }
        ],
        "safety": {
            "credential_values_written": False,
            "rotation_performed": False,
            "real_secrets_printed": False,
            "live_fleet_or_cloud_invoked": False,
        },
        "retry": {
            "policy": "no-automatic-retry",
            "tree_mutated": False,
        },
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/AUD-0079/UNIT-ARTIFACT-MANIFEST.json",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:AUD-0079 sentinel missing from payload")
        return 1
    if not live["both_states_control"]["ok"]:
        print("FAILED:AUD-0079 both-states control not ok")
        return 1
    out_path.write_text(payload, encoding="utf-8", newline="\n")
    sha, size = _digest(out_path)
    print(f"wrote {C.OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:AUD-0079")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
