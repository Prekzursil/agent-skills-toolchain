"""IMP-0218: HumanCheckpoint owner gate - persist, emit, exit; never busy-wait."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from agentspec.checkpoint import (
    OwnerQuestion,
    assert_no_busy_wait,
    owner_gate_pause,
)
from agentspec.spec import HumanCheckpoint

QUESTION = OwnerQuestion(
    checkpoint_id="cp-foundation",
    question="Which execution substrate should the wave-2 fleet default to: worktree-isolated or local-serialized?",
    recommendation="worktree-isolated",
    tradeoff="Higher disk and setup cost per agent; a shared checkout is faster but agents contaminate each other's index (measured 2026-07).",
    default="worktree-isolated",
    options=("worktree-isolated", "local-serialized"),
)


def _checkpoint() -> HumanCheckpoint:
    return HumanCheckpoint(
        id="cp-foundation",
        prompt_ref="_USER-PROMPTS.md:11364-11370",
        allowed_responses=("approve", "redirect"),
        default_if_unanswered="worktree-isolated",
        pause_token="tok-foundation",
    )


def test_gate_persists_and_emits_without_waiting() -> None:
    with tempfile.TemporaryDirectory() as td:
        env = owner_gate_pause(_checkpoint(), td, QUESTION)
        # returns immediately (no wait primitive in the call path); envelope complete
        assert env["status"] == "paused" and env["terminal"] is True
        rec = json.loads((Path(td) / "pause.json").read_text(encoding="utf-8"))
        assert rec["question"]["recommendation"] == "worktree-isolated"
        assert rec["question"]["default"] == "worktree-isolated"
        assert rec["pause_token"] == "tok-foundation"
        assert env["durable_record"] == str(Path(td) / "pause.json")


def test_no_busy_wait_static_control() -> None:
    import agentspec.checkpoint as cp

    src = Path(cp.__file__).read_text(encoding="utf-8")
    gate_src = "def owner_gate_pause" + src.split("def owner_gate_pause", 1)[1].split(chr(10) + "def ", 1)[0]
    verdict = assert_no_busy_wait(gate_src)
    assert verdict["clean"] is True, f"gate contains waiting primitives: {verdict['banned_hits']}"


def test_resume_flow_completes_after_owner_answer() -> None:
    from agentspec.checkpoint import run_workflow
    from agentspec.envelope import STATUS_COMPLETED

    cp = _checkpoint()
    wf = type("W", (), {"nodes": (cp,)})()
    with tempfile.TemporaryDirectory() as td:
        first = run_workflow(wf, td)
        assert first.status == "paused"
        second = run_workflow(
            wf, td, resume_token="tok-foundation", owner_response="approve"
        )
        assert second.status == STATUS_COMPLETED
