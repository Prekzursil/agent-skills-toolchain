#!/usr/bin/env python3
"""pytest tests for dark-surface/check.py (Stop hook — GREEN-not-LIVE stub nudge).

Run:
    pytest hooks/dark-surface/test_dark_surface.py -v

Hermetic: TEMP/TMP/TMPDIR are pointed at a tmp dir so the hook's per-session
``edit-validate/{sid}.edits`` file and the SI-2 shadow sink never touch real state.
The EDITED SOURCE FILE lives in a NEUTRAL-named temp dir (``src_dir`` fixture) — not
under pytest's ``test_<func>`` tmp dir — because dark-surface's TEST_HINT regex would
otherwise (correctly, in production terms) skip any path with a ``test_`` segment.

Covers the A6 SHADOW default (observe-only [SHADOW] note + SI-2 sink record), the
legacy plain nudge (DARK_SURFACE_MODE=live), the opt-out, the no-claim / no-stub
silence, anti-loop, and fail-open on garbage stdin.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HOOK = str(Path(__file__).resolve().parent / "check.py")

_STUB_SRC = "def feature():\n    raise NotImplementedError  # not wired yet\n"
_CLEAN_SRC = "def feature():\n    return 42\n"
_DONE_CLAIM = "I implemented the feature and wired it up end to end."


@pytest.fixture
def src_dir():
    """A neutral-named temp dir for edited source files (no 'test_' segment)."""
    d = Path(tempfile.mkdtemp(prefix="ds-src-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _write_transcript(path: Path, text: str) -> None:
    ev = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }
    path.write_text(json.dumps(ev) + "\n", encoding="utf-8")


def _write_edits(tmp: Path, sid: str, files: list[str]) -> None:
    d = tmp / "edit-validate"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sid}.edits").write_text("\n".join(files) + "\n", encoding="utf-8")


def _run(
    payload: dict, tmp: Path, env_extra: dict | None = None
) -> tuple[int, str, str]:
    env = dict(os.environ)
    # Make tempfile.gettempdir() resolve to our tmp dir (hermetic edits + sink).
    env["TEMP"] = env["TMP"] = env["TMPDIR"] = str(tmp)
    env.pop("DARK_SURFACE", None)
    env.pop("DARK_SURFACE_MODE", None)
    env.pop("HARNESS_SHADOW_DIR", None)
    env["HARNESS_SHADOW_SAMPLE"] = "1"
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _ctx(out: str) -> str:
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


def _setup(tmp: Path, src: Path, body: str = _STUB_SRC, claim: str = _DONE_CLAIM):
    sid = "sess-darksurface-1"
    f = src / "feature.py"
    f.write_text(body, encoding="utf-8")
    _write_edits(tmp, sid, [str(f)])
    tr = tmp / "transcript.jsonl"
    _write_transcript(tr, claim)
    return sid, tr


class TestShadowMode:
    def test_default_is_shadow_note_with_sink_record(self, tmp_path, src_dir):
        sid, tr = _setup(tmp_path, src_dir)
        sink = tmp_path / "shadow"
        rc, out, err = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {
                "HARNESS_SHADOW_DIR": str(sink)
            },  # DARK_SURFACE_MODE unset → default shadow
        )
        assert rc == 0
        assert err == ""
        ctx = _ctx(out)
        assert "[SHADOW]" in ctx
        assert "feature.py" in ctx
        files = list(sink.glob("shadow-*.jsonl"))
        assert files, "expected a would-have-fired record in the SI-2 shadow sink"
        rec = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
        assert rec["gate"] == "dark-surface"
        assert rec["tier"] == "heuristic"
        assert rec["event"] == "Stop"
        assert rec["reason_code"] == "dark_surface:stub_marker"
        assert set(rec.keys()) == {
            "ts",
            "gate",
            "tier",
            "event",
            "reason_code",
            "session_hash",
        }

    def test_live_mode_plain_note_no_sink(self, tmp_path, src_dir):
        sid, tr = _setup(tmp_path, src_dir)
        sink = tmp_path / "shadow"
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"DARK_SURFACE_MODE": "live", "HARNESS_SHADOW_DIR": str(sink)},
        )
        assert rc == 0
        ctx = _ctx(out)
        assert "[SHADOW]" not in ctx
        assert "dark-surface" in ctx
        assert not list(sink.glob("shadow-*.jsonl"))


class TestSilent:
    def test_no_completion_claim_silent(self, tmp_path, src_dir):
        sid, tr = _setup(
            tmp_path, src_dir, claim="Here is a summary of what remains to do."
        )
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        assert out == ""

    def test_no_stub_marker_silent(self, tmp_path, src_dir):
        sid, tr = _setup(tmp_path, src_dir, body=_CLEAN_SRC)
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        assert out == ""

    def test_opt_out_silent(self, tmp_path, src_dir):
        sid, tr = _setup(tmp_path, src_dir)
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"DARK_SURFACE": "off", "HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        assert out == ""


class TestFailOpen:
    def test_garbage_stdin_exit_0(self, tmp_path):
        env = dict(os.environ)
        env["TEMP"] = env["TMP"] = env["TMPDIR"] = str(tmp_path)
        p = subprocess.run(
            [sys.executable, HOOK],
            input="not json {{{",
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert p.returncode == 0
        assert p.stdout.strip() == ""

    def test_stop_hook_active_anti_loop(self, tmp_path, src_dir):
        sid, tr = _setup(tmp_path, src_dir)
        rc, out, _ = _run(
            {
                "session_id": sid,
                "transcript_path": str(tr),
                "cwd": str(tmp_path),
                "stop_hook_active": True,
            },
            tmp_path,
            {"HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        assert out == ""
