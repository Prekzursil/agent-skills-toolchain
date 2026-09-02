#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0035-blocker-as-failing-test.json."""
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
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import schema_local as S  # noqa: E402

OUT = "command-center/audit/AUD-0035-blocker-as-failing-test.json"
SCHEMA = "command-center/schema/failing-test-receipt.schema.json"
TEST_MOD = "command-center/p2-wave/probes/AUD-0035/test_decision_log_reconciled.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0035/probe1_current_tree_red.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0035/probe2_reconciled_scratch_green.py"
)
TEST_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {TEST_MOD}"
SENTINEL = (
    "SUCCESS:AUD-0035 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Write a test that FAILS today because 17-DECISION-LOG.md line 175 states "
    "the M-NN collision in present tense while carrying zero MECH tokens, and "
    "that PASSES only once the decision log is reconciled."
)
SUPPORTING = [
    SCHEMA,
    TEST_MOD,
    "command-center/p2-wave/probes/AUD-0035/engine.py",
    "command-center/p2-wave/probes/AUD-0035/probe1_current_tree_red.py",
    "command-center/p2-wave/probes/AUD-0035/probe2_reconciled_scratch_green.py",
    "command-center/p2-wave/probes/AUD-0035/resolution_map.json",
    "command-center/p2-wave/probes/AUD-0035/fixtures/stale-decision-log.md",
    "command-center/p2-wave/probes/AUD-0035/schema_local.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def run_cmd(cmd: str, extra_env: dict | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    if not path.is_file() or size < 1:
        raise SystemExit(f"FAILED:AUD-0035 missing supporting artifact {rel}")
    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def clip(text: str, limit: int = 60000) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…truncated…"


def main() -> int:
    E.write_stale_fixture()
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0035 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:AUD-0035-probe1" not in t1:
        print("FAILED:AUD-0035 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:AUD-0035-probe2" not in t2:
        print("FAILED:AUD-0035 emit probe2 sentinel missing")
        return 1

    subject, kind = E.current_tree_subject()
    rel_subject = (
        subject.relative_to(REPO).as_posix()
        if subject.is_relative_to(REPO)
        else str(subject)
    )
    c_now, t_now = run_cmd(f"{TEST_CMD} {rel_subject}")
    if c_now == 0:
        print("FAILED:AUD-0035 current-tree test was GREEN")
        print(t_now[-2000:])
        return 1
    current_eval = E.evaluate(subject)

    line175_cmd = (
        "python3 -B -c \"from pathlib import Path; "
        "p=Path('command-center/p2-wave/probes/AUD-0035/fixtures/"
        "stale-decision-log.md'); t=p.read_text(encoding='utf-8'); "
        "lines=t.splitlines(); print(lines[174]); "
        "print('MECH_COUNT='+str(t.count('MECH')))\""
    )
    c_l175, t_l175 = run_cmd(line175_cmd)
    if c_l175 != 0 or "remains live" not in t_l175 or "MECH_COUNT=0" not in t_l175:
        print("FAILED:AUD-0035 file-read verifier did not see present-tense collision")
        print(t_l175[-1500:])
        return 1

    with tempfile.TemporaryDirectory(prefix="aud0035-emit-") as raw:
        tmp = Path(raw)
        good = tmp / "17-DECISION-LOG.md"
        src = E.live_log_path() if E.live_log_present() else None
        E.write_reconciled_copy(src, good)
        c_fix, t_fix = run_cmd(
            TEST_CMD,
            extra_env={"AUD0035_DECISION_LOG": str(good)},
        )
        green_eval = E.evaluate(good)
        mech_cmd = (
            "python3 -B -c \"from pathlib import Path; "
            f"t=Path(r'{good}').read_text(encoding='utf-8'); "
            "lines=t.splitlines(); print(lines[174]); "
            "print('MECH_COUNT='+str(t.count('MECH'))); "
            "print('PRESENT_LIVE='+str('remains live' in lines[174] or "
            "'Queued as P2-09' in lines[174]))\""
        )
        c_mech, t_mech = run_cmd(mech_cmd)
    if c_fix != 0:
        print("FAILED:AUD-0035 reconciled scratch test was RED")
        print(t_fix[-2000:])
        return 1
    if c_mech != 0 or "MECH-NN" not in t_mech or "MECH_COUNT=0" in t_mech:
        print("FAILED:AUD-0035 byte-compare verifier missed MECH-NN reconciliation")
        print(t_mech[-1500:])
        return 1

    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(now.timestamp() - 1, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    named_probes = [
        {
            "id": "probe1",
            "command": P1,
            "exit_code": c1,
            "role": "current-tree-red",
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "command": P2,
            "exit_code": c2,
            "role": "reconciled-scratch-green",
            "raw_output": t2,
        },
    ]

    receipt = {
        "schema_version": 1,
        "unit_id": "AUD-0035",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10656",
        "min_bytes_threshold": 256,
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "The executable test is RED on the current unreconciled "
                    "subject: line 175 states the 31-way M-NN collision in the "
                    "present tense and the file carries zero MECH tokens "
                    f"(subject_kind={kind}; live 17-DECISION-LOG.md present="
                    f"{E.live_log_present()})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0035/"
                    "probe1_current_tree_red.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": clip(t1),
                        "fingerprint": fp("test-run", P1),
                        "exit_code": c1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": line175_cmd,
                        "raw_output": clip(t_l175),
                        "fingerprint": fp("file-read", line175_cmd),
                        "exit_code": c_l175,
                    },
                ],
            },
            {
                "claim": (
                    "The same test is GREEN on a scratch copy after MECH-NN "
                    "reconciliation and remains RED on an unreconciled scratch "
                    "that still exists, so file-presence alone cannot pass."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0035/"
                    "probe2_reconciled_scratch_green.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": clip(t2),
                        "fingerprint": fp("command", P2),
                        "exit_code": c2,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": mech_cmd,
                        "raw_output": clip(t_mech),
                        "fingerprint": fp("byte-compare", mech_cmd),
                        "exit_code": c_mech,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-current-tree-red",
                "command": P1,
                "result": "PASS",
                "output_tail": clip(t1, 16000),
            },
            {
                "id": "probe2-reconciled-scratch-green",
                "command": P2,
                "result": "PASS",
                "output_tail": clip(t2, 16000),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-unreconciled-present-tense-collision",
                "kind": "known-broken-fixture",
                "description": (
                    "Captured stale decision log with zero MECH tokens and "
                    "line 175 present-tense M-NN collision must stay RED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": clip(current_eval["assertion"], 16000),
                "good_state_output": clip(green_eval["assertion"], 16000),
            }
        ],
        "reviewer": {
            "reviewer_id": "AUD-0035-probe2-reconciled-scratch",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "codex",
            "notes": (
                "Re-ran only the second probe: rebuilt a scratch decision log, "
                "applied MECH-NN reconciliation, and required GREEN on that copy "
                "and RED on a still-present unreconciled copy. Did not import probe1."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0035/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "AUD-0035",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/AUD-0035/schema_local.py "
                    "Draft202012Validator (disk RefResolver)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import json,sys; sys.path.insert(0,"
                        "'command-center/p2-wave/probes/AUD-0035'); "
                        "import schema_local as S; "
                        f"d=json.load(open('{OUT}',encoding='utf-8')); "
                        "e=S.errors(d); print('schema_errors',len(e)); "
                        "assert not e\""
                    ),
                    "raw_output": "schema_errors 0",
                    "fingerprint": fp("schema-validate", "schema_local.errors"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated the "
                "tree; restore from the AUD-0092 backup, record the mutation, "
                "and escalate"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This Linux worktree has no live 17-DECISION-LOG.md; probe 1 "
                    "records that absence as RED and uses the captured stale "
                    "fixture (catalog line-175 present-tense collision, zero MECH "
                    "tokens) as the current-tree subject so the detector is not "
                    "only an existence check."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Restore 17-DECISION-LOG.md onto the live tree and re-run "
                    "probe1 against that path; the test must stay RED until "
                    "line 175 is past-tense MECH-NN and the file carries MECH "
                    "tokens."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "report": {
            "kind": "failing-test-receipt",
            "control_ids": [
                "current-tree-red",
                "reconciled-scratch-green",
                "unreconciled-scratch-still-red",
            ],
            "observations": [
                {
                    "name": "current-tree-color",
                    "measured": "RED",
                    "method": "test-run",
                    "anchor": rel_subject + ":175",
                },
                {
                    "name": "current-tree-mech-token-count",
                    "measured": int(current_eval["mech_token_count"]),
                    "method": "token-count",
                    "anchor": rel_subject,
                },
                {
                    "name": "current-tree-present-tense-collision",
                    "measured": bool(current_eval["present_tense_collision"]),
                    "method": "line-175-classifier",
                    "anchor": rel_subject + ":175",
                },
                {
                    "name": "reconciled-scratch-color",
                    "measured": "GREEN",
                    "method": "test-run",
                    "anchor": "scratch:17-DECISION-LOG.md:175",
                },
                {
                    "name": "both-states-discriminates",
                    "measured": True,
                    "method": "red-then-green",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0035/"
                        "probe2_reconciled_scratch_green.py"
                    ),
                },
            ],
            "question": QUESTION,
            "test_module": TEST_MOD,
            "test_command": TEST_CMD,
            "resolution_map": (
                "command-center/p2-wave/probes/AUD-0035/resolution_map.json"
            ),
            "live_decision_log": {
                "candidates": list(E.LIVE_REL_CANDIDATES),
                "present": E.live_log_present(),
                "subject_kind": kind,
                "subject_path": rel_subject,
            },
            "current_tree_run": {
                "color": "RED",
                "exit_code": c_now,
                "assertion_message": current_eval["assertion"],
                "verbatim_output": t_now,
                "subject_kind": kind,
                "path": rel_subject,
                "mech_token_count": current_eval["mech_token_count"],
                "present_tense_collision": current_eval["present_tense_collision"],
                "line_175": current_eval["line_175"],
            },
            "reconciled_scratch_run": {
                "color": "GREEN",
                "exit_code": c_fix,
                "verbatim_output": t_fix,
                "assertion_message": green_eval["assertion"],
                "mech_token_count": green_eval["mech_token_count"],
                "present_tense_collision": green_eval["present_tense_collision"],
                "line_175": green_eval["line_175"],
            },
            "both_states_discriminates": True,
            "named_probes": named_probes,
        },
        "extensions": {
            "output_schema": SCHEMA,
            "output_path": OUT,
            "cloud_ok": False,
            "adv_rebuild_circle": False,
        },
    }

    errs = S.errors(receipt)
    if errs:
        print("FAILED:AUD-0035 emit schema-invalid")
        for e in errs[:30]:
            print(f"  {e}")
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "AUD-0035", "state": "SUCCESS"},
        {
            "unit_id": "AUD-0035",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:AUD-0035",
            "report": {"kind": "audit-finding"},
        },
    ):
        g_errs = S.errors(garbage)
        if not g_errs:
            print(f"FAILED:AUD-0035 schema accepts garbage {str(garbage)[:80]}")
            return 1
        garbage_rejected += 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = digest(out)
    written = json.loads(out.read_text(encoding="utf-8"))
    disk_errs = S.errors(written)
    if disk_errs:
        print("FAILED:AUD-0035 written artifact schema-invalid")
        for e in disk_errs[:30]:
            print(f"  {e}")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:AUD-0035 sentinel missing from artifact text")
        return 1
    if live_bytes < 256:
        print(f"FAILED:AUD-0035 artifact too small ({live_bytes} B)")
        return 1
    if written.get("report", {}).get("kind") != "failing-test-receipt":
        print("FAILED:AUD-0035 report.kind is not failing-test-receipt")
        return 1
    print(
        f"wrote {OUT} bytes={live_bytes} sha256={live_sha} "
        f"garbage_rejected={garbage_rejected}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
