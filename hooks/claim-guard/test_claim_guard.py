#!/usr/bin/env python3
"""pytest tests for claim-guard (claim-check.py Stop hook + ledger-write.py PostToolUse).

Run:
    pytest hooks/claim-guard/test_claim_guard.py -v
    python -m pytest hooks/claim-guard/test_claim_guard.py -v

External-anchored, subprocess-level tests that mirror how Claude Code calls the
hooks (stdin JSON, env, exit code, stdout/stderr).

Covers:
  - Back-ported behaviour is unchanged: existing categories (tests / build / lint /
    fixed …) warn when unsupported and stay silent when a matching ok=true command
    exists; hedged phrasing stays silent.
  - G1 functional-acceptance category: warns with NO e2e evidence, stays silent
    with a real e2e/acceptance ok=true command, and STILL warns when only a plain
    `pytest` ok=true exists (proves the HIGHER external bar). Hedged functional
    phrasing stays silent.
  - CLAIM_GUARD_MODE=block: exit 2 ONLY for an unsupported functional claim; a
    non-functional unsupported claim stays WARN (exit 0) even in block mode.
  - DEFAULTS UNCHANGED: with NO env set, a functional claim warns (exit 0) and
    NEVER blocks (never exit 2). MODE=off silences everything.
  - Fail-open: any exception → exit 0, no output.
  - ledger-write.py records {cmd, ok} per Bash call and respects MODE=off.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
CHECK = str(HOOK_DIR / "claim-check.py")
LEDGER_WRITE = str(HOOK_DIR / "ledger-write.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ledger_name(session_id: str) -> str:
    """Mirror claim-check._ledger_file's session→filename sanitisation."""
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
        :80
    ]
    return f"{safe or 'unknown'}.ndjson"


def _write_ledger(root: Path, session_id: str, cmds: list[tuple[str, bool]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    p = root / _ledger_name(session_id)
    with p.open("w", encoding="utf-8") as fh:
        for cmd, ok in cmds:
            rec = {"ts": "t", "cmd": cmd, "exit": 0 if ok else 1, "ok": ok}
            fh.write(json.dumps(rec) + "\n")


def _transcript(root: Path, text: str) -> str:
    p = root / f"transcript-{uuid.uuid4().hex}.jsonl"
    ev = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }
    p.write_text(json.dumps(ev) + "\n", encoding="utf-8")
    return str(p)


def _run_check(
    tmp_path: Path,
    text: str,
    cmds: list[tuple[str, bool]] | None = None,
    mode: str | None = None,
    session_id: str = "s1",
    extra_env: dict | None = None,
    stdin_override: str | None = None,
) -> tuple[int, str, str]:
    root = tmp_path / "ledger"
    root.mkdir(parents=True, exist_ok=True)
    if cmds:
        _write_ledger(root, session_id, cmds)
    tp = _transcript(tmp_path, text)
    env = dict(os.environ)
    env["CLAIM_GUARD_LEDGER_ROOT"] = str(root)
    env.pop("CLAIM_GUARD_MODE", None)
    env.pop("CLAIM_GUARD_E2E_EXTRA", None)
    if mode is not None:
        env["CLAIM_GUARD_MODE"] = mode
    if extra_env:
        env.update(extra_env)
    if stdin_override is not None:
        payload = stdin_override
    else:
        payload = json.dumps({"session_id": session_id, "transcript_path": tp})
    p = subprocess.run(
        [sys.executable, CHECK],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _fired(out: str) -> bool:
    if not out:
        return False
    try:
        return "additionalContext" in json.loads(out).get("hookSpecificOutput", {})
    except Exception:
        return False


def _ctx(out: str) -> str:
    try:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Back-ported behaviour: existing categories unchanged
# ---------------------------------------------------------------------------


class TestExistingCategoriesUnchanged:
    def test_tests_claim_unsupported_warns(self, tmp_path):
        rc, out, _ = _run_check(tmp_path, "All tests pass now.")
        assert rc == 0
        assert _fired(out)
        assert "tests pass" in _ctx(out)

    def test_tests_claim_supported_by_pytest_silent(self, tmp_path):
        rc, out, _ = _run_check(
            tmp_path, "All tests pass now.", cmds=[("pytest tests/", True)]
        )
        assert rc == 0
        assert not _fired(out)

    def test_build_claim_unsupported_warns(self, tmp_path):
        rc, out, _ = _run_check(tmp_path, "The build succeeds.")
        assert rc == 0
        assert _fired(out)

    def test_fixed_claim_supported_by_any_ok_cmd_silent(self, tmp_path):
        rc, out, _ = _run_check(
            tmp_path, "The bug is now fixed.", cmds=[("echo done", True)]
        )
        assert rc == 0
        assert not _fired(out)

    def test_hedged_tests_claim_silent(self, tmp_path):
        rc, out, _ = _run_check(tmp_path, "The tests should pass once you run them.")
        assert rc == 0
        assert not _fired(out)

    def test_no_claim_silent(self, tmp_path):
        rc, out, _ = _run_check(tmp_path, "Here is a summary of what I changed.")
        assert rc == 0
        assert not _fired(out)


# ---------------------------------------------------------------------------
# G1: functional-acceptance category
# ---------------------------------------------------------------------------


class TestFunctionalCategory:
    def test_functional_no_evidence_warns(self, tmp_path):
        rc, out, _ = _run_check(tmp_path, "The app works end to end now.")
        assert rc == 0
        assert _fired(out)
        # Warning must NAME the gap (golden-journey / e2e / acceptance).
        ctx = _ctx(out).lower()
        assert "e2e" in ctx or "golden" in ctx or "acceptance" in ctx

    def test_functional_with_e2e_evidence_silent(self, tmp_path):
        rc, out, _ = _run_check(
            tmp_path,
            "The app works end to end now.",
            cmds=[("npx playwright test", True)],
        )
        assert rc == 0
        assert not _fired(out)

    def test_functional_with_only_pytest_still_warns(self, tmp_path):
        """A plain unit-test pass does NOT satisfy a functional claim (higher bar)."""
        rc, out, _ = _run_check(
            tmp_path, "The app works end to end now.", cmds=[("pytest tests/", True)]
        )
        assert rc == 0
        assert _fired(out)

    def test_functional_with_e2e_spec_path_silent(self, tmp_path):
        """An `e2e` spec path in the command counts as external evidence."""
        rc, out, _ = _run_check(
            tmp_path,
            "Shorts generate correctly now.",
            cmds=[("pytest tests/e2e/test_flow.py", True)],
        )
        assert rc == 0
        assert not _fired(out)

    def test_functional_with_golden_journey_silent(self, tmp_path):
        rc, out, _ = _run_check(
            tmp_path,
            "The flow works now.",
            cmds=[("npm run golden-journey", True)],
        )
        assert rc == 0
        assert not _fired(out)

    def test_functional_hedged_silent(self, tmp_path):
        rc, out, _ = _run_check(tmp_path, "The app should work end to end now.")
        assert rc == 0
        assert not _fired(out)

    def test_functional_env_extra_signature_silent(self, tmp_path):
        """CLAIM_GUARD_E2E_EXTRA lets a project add produced-artifact signatures."""
        rc, out, _ = _run_check(
            tmp_path,
            "The app now renders the video.",
            cmds=[("python -m media_studio render out.mp4", True)],
            extra_env={"CLAIM_GUARD_E2E_EXTRA": "media_studio"},
        )
        assert rc == 0
        assert not _fired(out)

    def test_functional_e2e_but_failed_still_warns(self, tmp_path):
        """An e2e command that FAILED (ok=false) is not evidence."""
        rc, out, _ = _run_check(
            tmp_path,
            "The app works end to end now.",
            cmds=[("npx playwright test", False)],
        )
        assert rc == 0
        assert _fired(out)


# ---------------------------------------------------------------------------
# CLAIM_GUARD_MODE=block — narrow: only unsupported functional claims
# ---------------------------------------------------------------------------


class TestBlockMode:
    def test_block_unsupported_functional_exits_2(self, tmp_path):
        rc, out, err = _run_check(
            tmp_path, "The app works end to end now.", mode="block"
        )
        assert rc == 2
        assert "block" in err.lower()
        assert "e2e" in err.lower() or "golden" in err.lower()

    def test_block_functional_with_e2e_evidence_silent(self, tmp_path):
        rc, out, err = _run_check(
            tmp_path,
            "The app works end to end now.",
            cmds=[("npx playwright test", True)],
            mode="block",
        )
        assert rc == 0
        assert not _fired(out)

    def test_block_does_not_block_non_functional_claim(self, tmp_path):
        """Block mode must NOT block a plain 'tests pass' claim — it stays warn."""
        rc, out, _ = _run_check(tmp_path, "All tests pass now.", mode="block")
        assert rc == 0
        assert _fired(out)

    def test_block_functional_with_only_pytest_exits_2(self, tmp_path):
        """A unit-test pass does not lift the functional block."""
        rc, _, err = _run_check(
            tmp_path,
            "The app works end to end now.",
            cmds=[("pytest tests/", True)],
            mode="block",
        )
        assert rc == 2
        assert "block" in err.lower()


# ---------------------------------------------------------------------------
# DEFAULTS UNCHANGED — no env set
# ---------------------------------------------------------------------------


class TestDefaultsUnchanged:
    def test_default_functional_warns_never_blocks(self, tmp_path):
        """With NO CLAIM_GUARD_MODE set, a functional claim warns (exit 0), never 2."""
        rc, out, _ = _run_check(tmp_path, "The app works end to end now.", mode=None)
        assert rc == 0  # never blocks by default
        assert _fired(out)

    def test_default_warn_mode_equivalent_to_no_env(self, tmp_path):
        rc, out, _ = _run_check(tmp_path, "The app works end to end now.", mode="warn")
        assert rc == 0
        assert _fired(out)


# ---------------------------------------------------------------------------
# Fail-open + off
# ---------------------------------------------------------------------------


class TestFailOpenAndOff:
    def test_garbage_stdin_exit_0(self, tmp_path):
        rc, out, _ = _run_check(
            tmp_path, "irrelevant", stdin_override="not json at all {{{"
        )
        assert rc == 0
        assert out == ""

    def test_empty_stdin_exit_0(self, tmp_path):
        rc, out, _ = _run_check(tmp_path, "irrelevant", stdin_override="")
        assert rc == 0

    def test_off_mode_silent(self, tmp_path):
        rc, out, _ = _run_check(tmp_path, "The app works end to end now.", mode="off")
        assert rc == 0
        assert not _fired(out)

    def test_stop_hook_active_silent(self, tmp_path):
        root = tmp_path / "ledger"
        root.mkdir(parents=True, exist_ok=True)
        tp = _transcript(tmp_path, "All tests pass now.")
        env = dict(os.environ)
        env["CLAIM_GUARD_LEDGER_ROOT"] = str(root)
        env.pop("CLAIM_GUARD_MODE", None)
        payload = json.dumps(
            {"session_id": "s1", "transcript_path": tp, "stop_hook_active": True}
        )
        p = subprocess.run(
            [sys.executable, CHECK],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )
        assert p.returncode == 0
        assert p.stdout.strip() == ""

    def test_no_transcript_silent(self, tmp_path):
        env = dict(os.environ)
        env["CLAIM_GUARD_LEDGER_ROOT"] = str(tmp_path / "ledger")
        env.pop("CLAIM_GUARD_MODE", None)
        payload = json.dumps({"session_id": "s1"})
        p = subprocess.run(
            [sys.executable, CHECK],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )
        assert p.returncode == 0


# ---------------------------------------------------------------------------
# ledger-write.py (PostToolUse)
# ---------------------------------------------------------------------------


class TestLedgerWrite:
    def _run_lw(
        self, tmp_path, payload: dict, mode: str | None = None
    ) -> tuple[int, Path]:
        root = tmp_path / "ledger"
        env = dict(os.environ)
        env["CLAIM_GUARD_LEDGER_ROOT"] = str(root)
        env.pop("CLAIM_GUARD_MODE", None)
        if mode is not None:
            env["CLAIM_GUARD_MODE"] = mode
        p = subprocess.run(
            [sys.executable, LEDGER_WRITE],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )
        assert p.returncode == 0
        sid = str(payload.get("session_id") or "unknown")
        return p.returncode, root / _ledger_name(sid)

    def _records(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_records_ok_command(self, tmp_path):
        _, ledger = self._run_lw(
            tmp_path,
            {
                "session_id": "lw1",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/"},
                "tool_response": {"exit_code": 0, "stdout": "ok"},
            },
        )
        recs = self._records(ledger)
        assert len(recs) == 1
        assert recs[0]["cmd"] == "pytest tests/"
        assert recs[0]["ok"] is True

    def test_records_failed_command(self, tmp_path):
        _, ledger = self._run_lw(
            tmp_path,
            {
                "session_id": "lw2",
                "tool_name": "Bash",
                "tool_input": {"command": "false"},
                "tool_response": {"exit_code": 1, "stderr": "nope"},
            },
        )
        recs = self._records(ledger)
        assert len(recs) == 1
        assert recs[0]["ok"] is False

    def test_non_bash_not_recorded(self, tmp_path):
        _, ledger = self._run_lw(
            tmp_path,
            {
                "session_id": "lw3",
                "tool_name": "Read",
                "tool_input": {"file_path": "x"},
                "tool_response": {},
            },
        )
        assert self._records(ledger) == []

    def test_off_mode_does_not_record(self, tmp_path):
        _, ledger = self._run_lw(
            tmp_path,
            {
                "session_id": "lw4",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest"},
                "tool_response": {"exit_code": 0},
            },
            mode="off",
        )
        assert self._records(ledger) == []

    def test_garbage_stdin_fail_open(self, tmp_path):
        env = dict(os.environ)
        env["CLAIM_GUARD_LEDGER_ROOT"] = str(tmp_path / "ledger")
        p = subprocess.run(
            [sys.executable, LEDGER_WRITE],
            input="not json {{{",
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )
        assert p.returncode == 0
