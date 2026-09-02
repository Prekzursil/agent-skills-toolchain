"""Regression: a receipt from an EARLIER turn must not vouch for a later claim.

README.md promises evidence from the ledger "this turn", but the ledger file is
keyed by session_id alone and `_load_ledger` returned every record in it. So:

    turn 1: `pytest -q` exits 0            -> receipt written
    turn 2: no command runs, model says    -> checker emitted ZERO bytes
            "Tests pass."

An identical claim under a FRESH session emitted the 319-byte unverified-claim
warning, which is what proved the leak was turn scope and not a dead checker.

Stop is the turn boundary: `claim-check` appends a `{"turn_end": true}` marker on
every non-continuation Stop, and only records after the last marker count.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
WRITER = HERE / "ledger-write.py"
CHECKER = HERE / "claim-check.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def ledger_root(tmp_path):
    root = tmp_path / "claim-ledger"
    root.mkdir()
    return root


@pytest.fixture()
def transcript(tmp_path):
    path = tmp_path / "transcript.jsonl"
    path.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Tests pass."}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _run(hook: Path, payload: dict, root: Path) -> tuple[int, str]:
    env = dict(os.environ)
    env["CLAIM_GUARD_LEDGER_ROOT"] = str(root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return proc.returncode, proc.stdout


def _record_pytest_success(root: Path, session: str = "shared-session") -> None:
    rc, _ = _run(
        WRITER,
        {
            "tool_name": "Bash",
            "session_id": session,
            "tool_input": {"command": "pytest -q"},
            "tool_response": {"exit_code": 0, "stdout": "5 passed"},
        },
        root,
    )
    assert rc == 0


def _stop(root: Path, transcript: Path, session: str = "shared-session"):
    return _run(
        CHECKER,
        {"session_id": session, "transcript_path": str(transcript)},
        root,
    )


def _lines(root: Path, session: str = "shared-session") -> list[dict]:
    path = root / f"{session}.ndjson"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# --- the leak ----------------------------------------------------------------


def test_stale_turn_receipt_does_not_support_a_later_claim(ledger_root, transcript):
    _record_pytest_success(ledger_root)
    rc1, out1 = _stop(ledger_root, transcript)  # turn 1: supported -> silent
    assert (rc1, out1) == (0, "")

    rc2, out2 = _stop(ledger_root, transcript)  # turn 2: nothing ran
    assert rc2 == 0
    assert out2.strip(), "turn-2 claim was accepted on a turn-1 receipt"
    ctx = json.loads(out2)["hookSpecificOutput"]["additionalContext"]
    assert "Unverified success claim" in ctx


def test_same_turn_receipt_still_supports_the_claim(ledger_root, transcript):
    """Positive control -- an over-broad fix that ignores the ledger fails here."""
    _record_pytest_success(ledger_root)
    rc, out = _stop(ledger_root, transcript)
    assert (rc, out) == (0, "")


def test_fresh_session_control_still_warns(ledger_root, transcript):
    rc, out = _run(
        CHECKER,
        {"session_id": "fresh-session", "transcript_path": str(transcript)},
        ledger_root,
    )
    assert rc == 0
    assert "Unverified success claim" in out


def test_new_receipt_after_a_boundary_supports_the_next_turn(ledger_root, transcript):
    _record_pytest_success(ledger_root)
    _stop(ledger_root, transcript)  # closes turn 1
    _record_pytest_success(ledger_root)  # real work in turn 2
    rc, out = _stop(ledger_root, transcript)
    assert (rc, out) == (0, "")


# --- boundary mechanics ------------------------------------------------------


def test_stop_writes_one_boundary_marker(ledger_root, transcript):
    _record_pytest_success(ledger_root)
    _stop(ledger_root, transcript)
    markers = [r for r in _lines(ledger_root) if r.get("turn_end") is True]
    assert len(markers) == 1


def test_silent_stop_still_closes_the_turn(ledger_root, tmp_path):
    """A turn that made NO claim consumed its receipts too. If the boundary were
    only written on the warning path, the next turn would inherit them."""
    _record_pytest_success(ledger_root)
    quiet = tmp_path / "quiet.jsonl"
    quiet.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Here is the diff."}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rc, out = _stop(ledger_root, quiet)
    assert (rc, out) == (0, "")
    assert [r for r in _lines(ledger_root) if r.get("turn_end") is True]


def test_stop_hook_continuation_does_not_close_the_turn(ledger_root, transcript):
    """A continuation is the SAME turn; closing it would strand its receipts.

    Scans the WHOLE ledger root, not just this session's file. An earlier
    revision read `session_id` only AFTER the guard, so removing the guard wrote
    the boundary under the fallback `unknown` key and a single-file assertion
    passed against that mutant -- measured. `session_id` is now read before the
    guard (so the finally block sees the real one) and this scan covers the
    fallback key regardless.
    """
    _record_pytest_success(ledger_root)
    rc, out = _run(
        CHECKER,
        {
            "session_id": "shared-session",
            "transcript_path": str(transcript),
            "stop_hook_active": True,
        },
        ledger_root,
    )
    assert (rc, out) == (0, "")
    for path in ledger_root.glob("*.ndjson"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                assert json.loads(line).get("turn_end") is not True, path.name

    # ...and the behavioural consequence: the receipt is still live, so the real
    # Stop that follows the continuation still finds its own turn's evidence.
    assert _stop(ledger_root, transcript) == (0, "")


def test_receipts_carry_their_turn_index(ledger_root, transcript):
    _record_pytest_success(ledger_root)
    _stop(ledger_root, transcript)
    _record_pytest_success(ledger_root)
    turns = [r["turn"] for r in _lines(ledger_root) if "turn" in r]
    assert turns == [0, 1]


def test_boundary_key_is_shared_by_both_hooks():
    writer = _load(WRITER, "_test_claim_ledger_write")
    checker = _load(CHECKER, "_test_claim_check")
    assert writer.TURN_BOUNDARY_KEY == checker.TURN_BOUNDARY_KEY == "turn_end"


def test_current_turn_is_fail_open_on_a_missing_ledger(tmp_path):
    writer = _load(WRITER, "_test_claim_ledger_write_2")
    assert writer.current_turn(tmp_path / "nope.ndjson") == 0


def test_current_turn_skips_unparseable_lines(tmp_path):
    writer = _load(WRITER, "_test_claim_ledger_write_3")
    path = tmp_path / "l.ndjson"
    path.write_text(
        '{"turn_end": true}\nnot json\n\n{"cmd": "x"}\n{"turn_end": true}\n',
        encoding="utf-8",
    )
    assert writer.current_turn(path) == 2


def test_close_turn_on_a_missing_ledger_is_a_noop(ledger_root, transcript):
    """Nothing ran, so there is no turn to close and no file to create."""
    rc, _ = _stop(ledger_root, transcript, session="never-ran")
    assert rc == 0
    assert not (ledger_root / "never-ran.ndjson").exists()


def test_non_dict_stdin_is_fail_open(ledger_root):
    """A payload that parses to a non-object must not reach the boundary writer.

    `main()` reads session_id and the continuation flag OUTSIDE the try/except so
    the `finally` can see them; without an explicit shape check that would raise
    AttributeError from the finally block, escaping main() entirely and breaking
    the FAIL-OPEN contract with a traceback and a non-zero exit.
    """
    env = dict(os.environ)
    env["CLAIM_GUARD_LEDGER_ROOT"] = str(ledger_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for payload in ("[]", '"a string"', "12", "null"):
        proc = subprocess.run(
            [sys.executable, "-B", str(CHECKER)],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", ""), payload
    assert list(ledger_root.glob("*.ndjson")) == []
