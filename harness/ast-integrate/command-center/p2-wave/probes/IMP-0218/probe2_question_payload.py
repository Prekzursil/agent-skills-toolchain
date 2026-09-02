#!/usr/bin/env python3
"""IMP-0218 probe2: owner-packet fields + durable record + resume.

Field-by-field: recommendation, tradeoff, default, durable record, exactly one
foundation-level question. Negative control: a two-question packet and a
recommendation-less packet must fail the same checker. Resume must skip
completed units (re_dispatch_count == 0).
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
sys.path.insert(0, str(REPO / "tools/agentspec"))
from agentspec.owner_packet import check_owner_packet, foundation_question_count  # noqa: E402

EXECUTOR = REPO / "tools/agentspec/agentspec/human_checkpoint.py"
OUT = HERE / "probe2-question-payload.raw.json"
COMPLETED_SHA = "b" * 64


def _run(cmd: list[str], timeout: float = 8) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "tools/agentspec") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def main() -> int:
    two_q = {
        "questions": ["Ratify A2?", "Also pick a color?"],
        "recommendation": "Ratify A2",
        "tradeoff": "Delay vs reversibility",
        "default": "ratify",
        "durable_record": "/tmp/x",
    }
    missing_rec = {
        "question": "Ratify A2?",
        "recommendation": "",
        "tradeoff": "Delay vs reversibility",
        "default": "ratify",
        "durable_record": "/tmp/x",
    }
    two_q_errors = check_owner_packet(two_q)
    missing_errors = check_owner_packet(missing_rec)
    fired_two = any("foundation_question_count" in e for e in two_q_errors)
    fired_missing = any(e.endswith(":recommendation") for e in missing_errors)
    if not fired_two or not fired_missing:
        print(
            "FAILED:IMP-0218-probe2 negative control inert",
            two_q_errors,
            missing_errors,
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="imp-0218-p2-") as tmp:
        ws = Path(tmp)
        pause_cmd = [
            sys.executable,
            "-B",
            str(EXECUTOR),
            "pause",
            "--workspace",
            str(ws),
            "--checkpoint-id",
            "cp-owner-gate",
            "--prompt-ref",
            "owner.ratify-architecture",
            "--question",
            "Ratify architecture A2, or override it?",
            "--recommendation",
            "Ratify A2; downstream IMP units are staged against it.",
            "--tradeoff",
            "Override is reversible but freezes every unit that depends on ratification.",
            "--default",
            "ratify",
            "--allowed",
            "ratify",
            "override",
            "--completed",
            f"IMP-0131={COMPLETED_SHA}",
            "--completed",
            f"IMP-0129={COMPLETED_SHA}",
        ]
        ran = _run(pause_cmd)
        if ran.returncode != 0:
            print("FAILED:IMP-0218-probe2 pause", ran.returncode, ran.stdout, ran.stderr)
            return 1
        envelope = json.loads(ran.stdout)
        packet = envelope.get("owner_packet") or {}
        field_errors = check_owner_packet(packet)
        if field_errors:
            print("FAILED:IMP-0218-probe2 live packet", field_errors)
            return 1
        qcount = foundation_question_count(packet)
        if qcount != 1:
            print("FAILED:IMP-0218-probe2 question count", qcount)
            return 1
        required = {
            "question": packet.get("question"),
            "recommendation": packet.get("recommendation"),
            "tradeoff": packet.get("tradeoff"),
            "default": packet.get("default"),
            "durable_record": packet.get("durable_record"),
        }
        if any(not isinstance(v, str) or not v.strip() for v in required.values()):
            print("FAILED:IMP-0218-probe2 empty required field", required)
            return 1
        if packet.get("default") != "ratify":
            print("FAILED:IMP-0218-probe2 default mismatch", packet.get("default"))
            return 1

        durable = Path(packet["durable_record"])
        if not durable.is_file():
            print("FAILED:IMP-0218-probe2 durable record missing", durable)
            return 1
        pause = json.loads(durable.read_text(encoding="utf-8"))
        if pause.get("owner_packet", {}).get("question") != packet["question"]:
            print("FAILED:IMP-0218-probe2 durable record question mismatch")
            return 1
        completed = (pause.get("workflow_state") or {}).get("completed_units") or []
        if len(completed) != 2:
            print("FAILED:IMP-0218-probe2 completed units not persisted", completed)
            return 1

        token = envelope["pause_token"]
        resume = _run(
            [
                sys.executable,
                "-B",
                str(EXECUTOR),
                "resume",
                "--workspace",
                str(ws),
                "--token",
                token,
                "--answer",
                "override",
            ]
        )
        if resume.returncode != 0:
            print("FAILED:IMP-0218-probe2 resume", resume.returncode, resume.stdout, resume.stderr)
            return 1
        continuation = json.loads(resume.stdout)
        if continuation.get("re_dispatch_count") != 0:
            print("FAILED:IMP-0218-probe2 re-dispatch", continuation)
            return 1
        ledger_path = Path(continuation["resume_ledger_path"])
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        skips = [e for e in ledger.get("events") or [] if e.get("type") == "skip_completed"]
        redispatches = [e for e in ledger.get("events") or [] if e.get("re_dispatch") is True]
        if len(skips) != 2 or redispatches or ledger.get("re_dispatch_count") != 0:
            print("FAILED:IMP-0218-probe2 ledger", ledger)
            return 1
        if continuation.get("answer") != "override" or continuation.get("answer_source") != "owner":
            print("FAILED:IMP-0218-probe2 answer not recorded", continuation)
            return 1

        default_resume_ws = Path(tmp) / "default-arm"
        default_pause = _run(
            [
                sys.executable,
                "-B",
                str(EXECUTOR),
                "pause",
                "--workspace",
                str(default_resume_ws),
                "--checkpoint-id",
                "cp-default",
                "--prompt-ref",
                "owner.ratify-architecture",
                "--question",
                "Ratify architecture A2, or override it?",
                "--recommendation",
                "Ratify A2.",
                "--tradeoff",
                "Override delays dependents.",
                "--default",
                "ratify",
                "--allowed",
                "ratify",
                "override",
            ]
        )
        default_env = json.loads(default_pause.stdout)
        defaulted = _run(
            [
                sys.executable,
                "-B",
                str(EXECUTOR),
                "resume",
                "--workspace",
                str(default_resume_ws),
                "--token",
                default_env["pause_token"],
            ]
        )
        if defaulted.returncode != 0:
            print("FAILED:IMP-0218-probe2 default resume", defaulted.stdout, defaulted.stderr)
            return 1
        default_cont = json.loads(defaulted.stdout)
        if default_cont.get("answer") != "ratify" or default_cont.get("answer_source") != "default_if_unanswered":
            print("FAILED:IMP-0218-probe2 default not applied", default_cont)
            return 1

        good_silent = check_owner_packet(packet) == []
        doc = {
            "probe": "probe2-question-payload",
            "unit_id": "IMP-0218",
            "pass": True,
            "foundation_question_count": qcount,
            "fields": required,
            "field_errors": field_errors,
            "durable_record_exists": durable.is_file(),
            "durable_bytes": durable.stat().st_size,
            "resume_re_dispatch_count": continuation.get("re_dispatch_count"),
            "skipped_completed": [s.get("unit_id") for s in skips],
            "answer": continuation.get("answer"),
            "default_resume_answer": default_cont.get("answer"),
            "negative_control": {
                "two_question_fired": fired_two,
                "missing_recommendation_fired": fired_missing,
                "two_question_errors": two_q_errors,
                "missing_recommendation_errors": missing_errors,
                "good_packet_silent": good_silent,
            },
        }
        OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"qcount={qcount} rec={bool(required['recommendation'])} "
            f"tradeoff={bool(required['tradeoff'])} default={required['default']!r} "
            f"durable={durable.is_file()} re_dispatch={continuation.get('re_dispatch_count')} "
            f"two_q_fired={fired_two} missing_rec_fired={fired_missing}"
        )
        print("SUCCESS:IMP-0218-probe2 question payload recommendation/tradeoff/default/durable")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
