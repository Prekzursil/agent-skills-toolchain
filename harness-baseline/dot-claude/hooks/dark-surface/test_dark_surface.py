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


class TestUseVsMention:
    """Regression pins for the 2026-08-08 discriminator wiring.

    Every case here FIRED on the pre-wiring hook (verified both-states against
    ``backups/check.py.pre-guards``), so a silence below is a measured flip, not a
    probe that was quiet in both states. The two TP cases pin the opposite direction:
    they must keep firing, or the wiring has disarmed the gate.
    """

    # the shape of all six recorded fires: a marker spelled inside a STRING LITERAL
    _STRING_LITERAL_MARKER = (
        "CASES = [\n"
        '    {"id": "row-1", "text": "def f():\\n    # TODO: handle empty"},\n'
        "]\n\n\ndef build():\n    return CASES\n"
    )
    # _bp_data_4.py:475 in miniature -- a field whose value WARNS against placeholders
    _CONTRA_PROSE = (
        "RULES = {\n"
        '    "contra": "NOT for a placeholder or an example value (verify first)",\n'
        "}\n"
    )

    def test_marker_in_string_literal_is_silent(self, tmp_path, src_dir):
        sid, tr = _setup(tmp_path, src_dir, body=self._STRING_LITERAL_MARKER)
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        assert out == "", (
            "a `# TODO` inside a corpus string literal is data, not a stub"
        )

    def test_placeholder_inside_a_contra_string_is_silent(self, tmp_path, src_dir):
        sid, tr = _setup(tmp_path, src_dir, body=self._CONTRA_PROSE)
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        assert out == "", "the recorded _bp_data_4.py fire: `placeholder` in a string"

    def test_claim_only_inside_a_fence_is_not_a_claim(self, tmp_path, src_dir):
        """kind='claim' polarity: quoting the phrase is not asserting it."""
        quoted = (
            "Here is the pattern, quoted for the report:\n\n"
            "```python\n"
            'COMPLETION_RE = r"(implemented|wired up)"\n'
            "```\n\n"
            "Nothing is finished yet."
        )
        sid, tr = _setup(tmp_path, src_dir, claim=quoted)
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        assert out == ""

    def test_genuine_claim_in_prose_still_fires(self, tmp_path, src_dir):
        """The other half of the polarity: kind='marker' would have silenced THIS."""
        sid, tr = _setup(tmp_path, src_dir)  # real NotImplementedError + prose claim
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        assert "feature.py" in _ctx(out)

    @pytest.mark.parametrize(
        ("label", "body"),
        [
            # `~~...~~` marks an ABANDONED idea, not pending work
            (
                "struck-through",
                "def f():\n    # ~~placeholder handling~~ dropped in v2\n    return 1\n",
            ),
            # a compliance table in a comment describes OTHER code's gaps
            (
                "table-cell",
                "# | feature | status |\n# | export | placeholder |\ndef f():\n    return 1\n",
            ),
        ],
    )
    def test_kind_is_stub_not_marker(self, tmp_path, src_dir, label, body):
        """Pins the KIND, not just the silencing.

        `stub` and `marker` agree on every recorded fire (all six sat in string
        literals, which both kinds call a MENTION), so those cases cannot tell the two
        apart -- a `stub`->`marker` mutant SURVIVED the first mutation run. These two
        constructs are `stub`-only mention rules: under `marker` both return
        `marker:source-file` = USE and the hook fires.
        """
        sid, tr = _setup(tmp_path, src_dir, body=body)
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        assert out == "", f"{label} is a stub-kind MENTION; marker semantics would fire"

    def test_real_stub_wins_over_earlier_mentions(self, tmp_path, src_dir):
        """A file of mentions must not mask a genuine dark surface in a later file."""
        sid = "sess-darksurface-mixed"
        mention = src_dir / "corpus.py"
        mention.write_text(self._STRING_LITERAL_MARKER, encoding="utf-8")
        real = src_dir / "exporter.py"
        real.write_text(
            "def export_csv(rows):\n    raise NotImplementedError\n", encoding="utf-8"
        )
        _write_edits(tmp_path, sid, [str(mention), str(real)])
        tr = tmp_path / "transcript-mixed.jsonl"
        _write_transcript(tr, _DONE_CLAIM)
        rc, out, _ = _run(
            {"session_id": sid, "transcript_path": str(tr), "cwd": str(tmp_path)},
            tmp_path,
            {"HARNESS_SHADOW_DIR": str(tmp_path / "shadow")},
        )
        assert rc == 0
        ctx = _ctx(out)
        assert "exporter.py" in ctx
        assert "corpus.py" not in ctx


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
