#!/usr/bin/env python3
"""pytest tests for hooks/checkpoint (PreCompact writer + SessionStart recovery).

Run:  pytest hooks/checkpoint/test_checkpoint_state.py -v

Hermetic: every test pins CHECKPOINT_BEADS_ROOT at a tmp dir and sets CHECKPOINT_SKIP_GIT=1, so
no live `.beads/`, no live transcript and no git subprocess is ever touched.

NOTE ON THE FILENAME: `hooks/edit-checkpoints/test_checkpoint.py` already exists, and pytest
raises `import file mismatch` for two same-named test modules in a rootdir with no packages.
This file is `test_checkpoint_state.py` for that reason -- renaming it back would turn the
whole hooks-tree run RED.

The end-to-end acceptance proof (subprocess-isolated, both-states, reconstruct-from-disk-only)
lives in `prove_recovery.py`, which is deliberately NOT a `test_*` module: it is a standalone
executable receipt, and pytest collecting it would hide its terminal-state output.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checkpoint_state as state  # noqa: E402

SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee"
FAKE_TOKEN = (
    "gh" + "p_" + "ZzYyXxWwVvUuTtSsRrQqPpOoNnMmLlKkJj"
)  # PLACEHOLDER, not a real key


@pytest.fixture
def beads(tmp_path, monkeypatch):
    root = tmp_path / "beadsroot"
    monkeypatch.setenv("CHECKPOINT_BEADS_ROOT", str(root))
    monkeypatch.setenv("CHECKPOINT_SKIP_GIT", "1")
    monkeypatch.delenv("CHECKPOINT_MAX_CONTEXT", raising=False)
    monkeypatch.delenv("CHECKPOINT_STALE_HOURS", raising=False)
    return root


def _transcript(
    tmp_path: Path, sid: str = SID, extra_text: str = "midway through step 7"
) -> Path:
    p = tmp_path / "t.jsonl"
    recs = [
        {
            "type": "user",
            "sessionId": sid,
            "gitBranch": "wip",
            "version": "2.1.214",
            "message": {"role": "user", "content": "go"},
        },
        {
            "type": "assistant",
            "sessionId": sid,
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "working"},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/srv/mod.py"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "command": f"curl -H 'Authorization: Bearer {FAKE_TOKEN}' https://x.invalid"
                        },
                    },
                    {
                        "type": "tool_use",
                        "name": "TodoWrite",
                        "input": {
                            "todos": [
                                {
                                    "content": "finish the migration",
                                    "status": "in_progress",
                                }
                            ]
                        },
                    },
                ],
            },
        },
        {
            "type": "last-prompt",
            "sessionId": sid,
            "lastPrompt": "please finish the migration",
        },
        {
            "type": "assistant",
            "sessionId": sid,
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": extra_text}],
            },
        },
    ]
    p.write_text(
        "\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8", newline="\n"
    )
    return p


def _event(tmp_path: Path, **over) -> dict:
    ev = {
        "session_id": SID,
        "cwd": str(tmp_path),
        "transcript_path": str(_transcript(tmp_path)),
        "trigger": "auto",
    }
    ev.update(over)
    return ev


# ---- typed vocabulary --------------------------------------------------------------------
def test_typed_vocabulary_is_exactly_the_p2_01_set():
    assert {
        state.FINDING,
        state.CLEAN,
        state.NOT_CHECKED,
        state.RAISED,
        state.DEGRADED,
    } == {"FINDING", "CLEAN", "NOT-CHECKED", "RAISED", "DEGRADED"}


# ---- path policy -------------------------------------------------------------------------
def test_env_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_BEADS_ROOT", str(tmp_path / "x"))
    path, present = state.state_path_for(str(tmp_path))
    assert path == tmp_path / "x" / "context" / "execution-state.md"
    assert present is True


def test_existing_beads_dir_is_used(tmp_path, monkeypatch):
    monkeypatch.delenv("CHECKPOINT_BEADS_ROOT", raising=False)
    (tmp_path / ".beads").mkdir()
    path, present = state.state_path_for(str(tmp_path))
    assert path == tmp_path / ".beads" / "context" / "execution-state.md"
    assert present is True


def test_absent_beads_falls_back_and_does_not_invent_a_beads_tree(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("CHECKPOINT_BEADS_ROOT", raising=False)
    monkeypatch.delenv("CHECKPOINT_CREATE_BEADS", raising=False)
    path, present = state.state_path_for(str(tmp_path))
    assert present is False
    assert ".beads" not in str(path)
    assert not (tmp_path / ".beads").exists()


# ---- redaction ---------------------------------------------------------------------------
def test_local_redactor_kills_a_bare_token():
    assert FAKE_TOKEN not in state._local_redact(f"export T={FAKE_TOKEN}")


def test_local_redactor_kills_a_json_password_value():
    out = state._local_redact('{"password": "sup3rsecret-pw"}')
    assert "sup3rsecret-pw" not in out and "password" in out


def test_local_redactor_is_not_a_no_op_detector_control():
    """Both-states control for the redactor: benign text must pass through UNCHANGED.

    A redactor that mangles everything would pass the two tests above while destroying the
    checkpoint's usefulness; a redactor that changes nothing would fail them. Only a detector
    that discriminates passes all three.
    """
    benign = "migrate shards 3-9 and keep the old index readable"
    assert state._local_redact(benign) == benign


def test_written_state_never_carries_a_planted_credential(tmp_path, beads):
    state.write_execution_state(_event(tmp_path))
    disk = (beads / "context" / "execution-state.md").read_text(encoding="utf-8")
    assert FAKE_TOKEN not in disk
    assert "finish the migration" in disk  # ...and the useful content DID survive


# ---- front-matter safety -----------------------------------------------------------------
def test_oneline_cannot_break_the_front_matter():
    assert "\n" not in state._oneline("a\nb\r\nc")
    assert not state._oneline("--- injected: yes").startswith("---")


def test_render_read_round_trip(tmp_path, beads):
    cap = state.capture(_event(tmp_path))
    text = state.render(cap, compaction_seq=3, history=["#2 earlier"])
    p = tmp_path / "s.md"
    p.write_text(text, encoding="utf-8")
    front, body = state.read_execution_state(p)
    assert front["schema"] == state.SCHEMA
    assert front["session_id"] == SID
    assert front["compaction_seq"] == "3"
    assert "#2 earlier" in body


# ---- capture / write ---------------------------------------------------------------------
def test_capture_flags_an_unreadable_transcript_rather_than_pretending_it_is_empty(
    tmp_path, beads
):
    cap = state.capture(_event(tmp_path, transcript_path=str(tmp_path / "nope.jsonl")))
    assert "transcript-unreadable" in cap["degraded"]
    assert cap["mined_ok"] is False


def test_write_returns_RAISED_and_creates_the_file(tmp_path, beads):
    res = state.write_execution_state(_event(tmp_path))
    assert res["state"] == state.RAISED
    assert Path(res["path"]).is_file()
    assert res["compaction_seq"] == 1


def test_write_returns_DEGRADED_when_capture_was_incomplete(tmp_path, beads):
    res = state.write_execution_state(_event(tmp_path, transcript_path=""))
    assert res["state"] == state.DEGRADED
    assert "transcript-unreadable" in res["reason"]
    assert Path(res["path"]).is_file(), (
        "a DEGRADED capture must still leave a truthful file"
    )


def test_unwritable_target_reports_NOT_CHECKED_not_silence(tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not dir", encoding="utf-8")
    monkeypatch.setenv("CHECKPOINT_BEADS_ROOT", str(blocker / "nope"))
    monkeypatch.setenv("CHECKPOINT_SKIP_GIT", "1")
    res = state.write_execution_state(_event(tmp_path))
    assert res["state"] == state.NOT_CHECKED
    assert res["reason"].startswith("write-failed:")


def test_compaction_seq_increments_and_history_is_kept(tmp_path, beads):
    state.write_execution_state(_event(tmp_path))
    res = state.write_execution_state(_event(tmp_path))
    assert res["compaction_seq"] == 2
    disk = Path(res["path"]).read_text(encoding="utf-8")
    assert "#1 " in disk and "#2 " in disk


def test_write_survives_a_garbage_event(tmp_path, beads):
    assert state.write_execution_state({})["state"] in {
        state.RAISED,
        state.DEGRADED,
        state.NOT_CHECKED,
    }
    assert state.write_execution_state(None)["state"] in {
        state.RAISED,
        state.DEGRADED,
        state.NOT_CHECKED,
    }


# ---- recovery ------------------------------------------------------------------------------
def test_missing_checkpoint_on_a_recovery_path_is_a_FINDING(tmp_path, beads):
    for src in ("compact", "resume", "clear"):
        verdict, ctx = state.recover(
            {"session_id": SID, "cwd": str(tmp_path), "source": src}
        )
        assert verdict == state.FINDING, src
        assert "no checkpoint" in ctx


def test_missing_checkpoint_on_a_fresh_start_is_CLEAN_and_silent(tmp_path, beads):
    verdict, ctx = state.recover(
        {"session_id": SID, "cwd": str(tmp_path), "source": "startup"}
    )
    assert verdict == state.CLEAN
    assert ctx is None


def test_same_session_checkpoint_is_RAISED_with_the_content(tmp_path, beads):
    state.write_execution_state(_event(tmp_path))
    verdict, ctx = state.recover(
        {"session_id": SID, "cwd": str(tmp_path), "source": "compact"}
    )
    assert verdict == state.RAISED
    assert "finish the migration" in ctx
    assert "UNTRUSTED historical content" in ctx


def test_foreign_session_is_DEGRADED_and_leaks_nothing(tmp_path, beads):
    state.write_execution_state(_event(tmp_path))
    verdict, ctx = state.recover(
        {"session_id": OTHER, "cwd": str(tmp_path), "source": "compact"}
    )
    assert verdict == state.DEGRADED
    assert "finish the migration" not in ctx
    assert "DIFFERENT session" in ctx


def test_stale_checkpoint_is_DEGRADED_and_withholds_content(
    tmp_path, beads, monkeypatch
):
    state.write_execution_state(_event(tmp_path))
    p = beads / "context" / "execution-state.md"
    old = (datetime.now(timezone.utc) - timedelta(hours=200)).isoformat(
        timespec="seconds"
    )
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            [
                ln
                for ln in p.read_text(encoding="utf-8").splitlines()
                if ln.startswith("timestamp:")
            ][0],
            f"timestamp: {old}",
        ),
        encoding="utf-8",
    )
    verdict, ctx = state.recover(
        {"session_id": SID, "cwd": str(tmp_path), "source": "compact"}
    )
    assert verdict == state.DEGRADED
    assert "finish the migration" not in ctx


def test_unparseable_checkpoint_is_DEGRADED(tmp_path, beads):
    p = beads / "context" / "execution-state.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not front matter\n", encoding="utf-8")
    verdict, ctx = state.recover(
        {"session_id": SID, "cwd": str(tmp_path), "source": "compact"}
    )
    assert verdict == state.DEGRADED
    assert "unparseable" in ctx


def test_recover_never_raises_on_a_garbage_event():
    for bad in (None, [], "nope", {"cwd": 12}):
        verdict, _ = state.recover(bad)
        assert verdict in {
            state.FINDING,
            state.CLEAN,
            state.DEGRADED,
            state.RAISED,
            state.NOT_CHECKED,
        }


def test_injected_context_respects_the_char_budget(tmp_path, beads, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_MAX_CONTEXT", "600")
    state.write_execution_state(
        _event(
            tmp_path, transcript_path=str(_transcript(tmp_path, extra_text="x" * 5000))
        )
    )
    verdict, ctx = state.recover(
        {"session_id": SID, "cwd": str(tmp_path), "source": "compact"}
    )
    assert verdict == state.RAISED
    assert len(ctx) <= 600


# ---- hook entry points (subprocess: the real wire) -------------------------------------------
def _run(script: str, payload: dict, env: dict) -> subprocess.CompletedProcess:
    import os

    full = dict(os.environ)
    full["PYTHONIOENCODING"] = "utf-8"
    full.update(env)
    return subprocess.run(
        [sys.executable, str(HERE / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full,
        timeout=120,
    )


def test_precompact_entry_point_exits_0_and_suppresses_output(tmp_path):
    env = {"CHECKPOINT_BEADS_ROOT": str(tmp_path / "r"), "CHECKPOINT_SKIP_GIT": "1"}
    proc = _run("precompact.py", _event(tmp_path), env)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["suppressOutput"] is True
    assert "CHECKPOINT-WRITE:" in proc.stderr


def test_precompact_exits_0_on_garbage_stdin(tmp_path):
    env = {"CHECKPOINT_BEADS_ROOT": str(tmp_path / "r"), "CHECKPOINT_SKIP_GIT": "1"}
    proc = subprocess.run(
        [sys.executable, str(HERE / "precompact.py")],
        input="}{not json",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env={**__import__("os").environ, **env, "PYTHONIOENCODING": "utf-8"},
    )
    assert proc.returncode == 0


def test_recover_entry_point_emits_sessionstart_shape(tmp_path):
    env = {"CHECKPOINT_BEADS_ROOT": str(tmp_path / "r"), "CHECKPOINT_SKIP_GIT": "1"}
    _run("precompact.py", _event(tmp_path), env)
    proc = _run(
        "recover.py",
        {"session_id": SID, "cwd": str(tmp_path), "source": "compact"},
        env,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert payload["hookSpecificOutput"]["additionalContext"]
    assert "CHECKPOINT-RECOVER: RAISED" in proc.stderr


# ---- wire.py: the wiring detector needs its own both-states control -------------------------
import wire  # noqa: E402


def _fixtures(tmp_path, *, pre: bool, rec_settings: bool, rec_dispatch: bool):
    s = {"hooks": {"PreCompact": [], "SessionStart": []}}
    if pre:
        s["hooks"]["PreCompact"].append(wire.PRECOMPACT_ENTRY)
    if rec_settings:
        s["hooks"]["SessionStart"].append(wire.SESSIONSTART_ENTRY)
    m = {
        "events": {
            "SessionStart": {"checks": ([wire.DISPATCH_CHECK] if rec_dispatch else [])}
        }
    }
    sp, mp = tmp_path / "settings.json", tmp_path / "manifest.json"
    sp.write_text(json.dumps(s), encoding="utf-8")
    mp.write_text(json.dumps(m), encoding="utf-8")
    return sp, mp


def test_wire_detector_reports_NOT_WIRED_in_the_known_broken_state(tmp_path):
    sp, mp = _fixtures(tmp_path, pre=False, rec_settings=False, rec_dispatch=False)
    verdict, why = wire.summarize(wire.check(sp, mp))
    assert verdict == "FINDING" and "NEITHER" in why


def test_wire_detector_reports_CLEAN_in_the_fixed_state_via_dispatch(tmp_path):
    """The fixed half of the both-states pair. Without this, --check could be a no-op that
    always says NOT-WIRED and nobody would notice until after the wiring was applied."""
    sp, mp = _fixtures(tmp_path, pre=True, rec_settings=False, rec_dispatch=True)
    verdict, _ = wire.summarize(wire.check(sp, mp))
    assert verdict == "CLEAN"


def test_wire_detector_reports_CLEAN_in_the_fixed_state_via_settings(tmp_path):
    sp, mp = _fixtures(tmp_path, pre=True, rec_settings=True, rec_dispatch=False)
    verdict, _ = wire.summarize(wire.check(sp, mp))
    assert verdict == "CLEAN"


def test_wire_detector_flags_a_half_wired_pair(tmp_path):
    sp, mp = _fixtures(tmp_path, pre=True, rec_settings=False, rec_dispatch=False)
    verdict, why = wire.summarize(wire.check(sp, mp))
    assert verdict == "FINDING" and "READER is not" in why


def test_wire_detector_reports_NOT_CHECKED_when_a_surface_is_unreadable(tmp_path):
    verdict, _ = wire.summarize(
        wire.check(tmp_path / "absent.json", tmp_path / "absent2.json")
    )
    assert verdict == "NOT-CHECKED"


def test_wire_has_no_apply_mode(tmp_path, capsys):
    """Applying from a lane that does not own settings.json is how a sibling's edit is lost.

    USE-vs-MENTION: the first version of this test grepped the source for the string `--apply`
    and failed on the docstring that EXPLAINS its absence -- the 17th instance of that error
    class in this program. The subject of the rule is the argparse SURFACE, not the prose, so
    that is what is asserted.
    """
    assert not hasattr(wire, "apply")
    with pytest.raises(SystemExit) as exc:
        wire.main(["--apply"])
    assert exc.value.code != 0  # argparse rejects the unknown option
    assert "unrecognized arguments" in capsys.readouterr().err


def test_disabled_marker_stops_both_halves(tmp_path):
    marker = HERE / ".disabled"
    env = {"CHECKPOINT_BEADS_ROOT": str(tmp_path / "r"), "CHECKPOINT_SKIP_GIT": "1"}
    marker.write_text("test", encoding="utf-8")
    try:
        w = _run("precompact.py", _event(tmp_path), env)
        r = _run(
            "recover.py",
            {"session_id": SID, "cwd": str(tmp_path), "source": "compact"},
            env,
        )
        assert "NOT-CHECKED disabled" in w.stderr
        assert "NOT-CHECKED disabled" in r.stderr
        assert r.stdout.strip() == ""
    finally:
        marker.unlink(missing_ok=True)
