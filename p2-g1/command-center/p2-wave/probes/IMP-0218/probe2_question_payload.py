"""IMP-0218 probe 2 (verifier): the emitted question carries recommendation, tradeoff,
default and a durable record - asserted field-by-field.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0218/probe2_question_payload.py
Exit 0 iff every contract field is present and non-empty on BOTH the terminal envelope
and the re-read durable record, and the question is exactly ONE foundation-level question.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))
from agentspec.checkpoint import OwnerQuestion, owner_gate_pause  # noqa: E402
from agentspec.spec import HumanCheckpoint  # noqa: E402

q = OwnerQuestion(
    checkpoint_id="cp-foundation",
    question="Which execution substrate should the wave-2 fleet default to: worktree-isolated or local-serialized?",
    recommendation="worktree-isolated",
    tradeoff="Higher disk and setup cost per agent; a shared checkout is faster but agents contaminate each other's index (measured 2026-07).",
    default="worktree-isolated",
    options=("worktree-isolated", "local-serialized"),
)
cp = HumanCheckpoint(
    id="cp-foundation", prompt_ref="_USER-PROMPTS.md:11364-11370",
    allowed_responses=("approve", "redirect"),
    default_if_unanswered="worktree-isolated", pause_token="tok-foundation",
)

with tempfile.TemporaryDirectory() as td:
    env = owner_gate_pause(cp, td, q)
    durable = Path(env["durable_record"])
    rec = json.loads(durable.read_text(encoding="utf-8"))
    fields = {
        "one_question_text": isinstance(env["question_text"], str) and env["question_text"].count("?") == 1,
        "recommendation": bool(env["recommendation"]),
        "tradeoff": bool(env["tradeoff"]),
        "default": bool(env["default"]),
        "durable_record_exists": durable.is_file() and durable.stat().st_size > 0,
        "record_roundtrip": rec["question"]["recommendation"] == env["recommendation"]
        and rec["question"]["default"] == env["default"]
        and rec["question"]["tradeoff"] == env["tradeoff"],
        "resume_token_bound": rec["pause_token"] == env["pause_token"] == "tok-foundation",
        "terminal_envelope": env["status"] == "paused" and env["terminal"] is True,
    }
ok = all(fields.values())

out = {"probe": "probe2-question-payload-fields", "unit_id": "IMP-0218",
       "fields": fields, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-payload.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0218-probe2 missing fields: %s" % [k for k, v in fields.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0218-probe2 question payload complete field-by-field with durable record")
