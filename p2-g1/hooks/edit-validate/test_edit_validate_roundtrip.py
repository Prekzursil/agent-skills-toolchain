"""Behavioural regression for the edit-validate producer -> Stop consumer contract.

Before this suite there was NO test that invoked either endpoint. The only place
the ledger appeared in a test was `hooks/dark-surface/test_dark_surface.py`,
whose `_write_edits` helper FABRICATES `<sid>.edits` itself and so exercises
neither `record.py` nor `validate-stop.py`. The census in
`hooks/_dispatch/test_wiring.py` is declarative (names + xfail text), not
behavioural. A rename of the ledger path, a change to the session-id
sanitisation, or a dropped tool_name would all have shipped green.

What is pinned here is the CONTRACT between the two halves, exercised end to end
as subprocesses: producer writes -> consumer reads the SAME path -> consumer
blocks on a genuinely broken file, stays silent on a healthy one, consumes the
ledger, and never re-nudges the same breakage.

Note on `TMPDIR`: `_validate` deliberately skips files under the system temp dir
(abandoned scratch helpers are not deliverables). The hooks are therefore run
with temp REDIRECTED to `<tmp_path>/systmp` while the edited files live in
`<tmp_path>/work`, so the fixture file is a real deliverable from the hook's
point of view while the ledger still lands in an isolated temp.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
RECORD = HERE / "record.py"
VALIDATE = HERE / "validate-stop.py"

SESSION = "s/1"
SANITISED = "s_1"


@pytest.fixture()
def sandbox(tmp_path):
    systmp = tmp_path / "systmp"
    work = tmp_path / "work"
    systmp.mkdir()
    work.mkdir()
    return systmp, work


def _env(systmp: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in ("TMPDIR", "TEMP", "TMP"):
        env[key] = str(systmp)
    env.pop("STOP_VALIDATE", None)
    return env


def _run(hook: Path, payload: dict, systmp: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-B", str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_env(systmp),
        timeout=120,
    )
    return proc.returncode, proc.stdout


def _record(systmp: Path, file_path: str, tool_name: str = "Edit") -> tuple[int, str]:
    return _run(
        RECORD,
        {
            "tool_name": tool_name,
            "tool_input": {"file_path": file_path},
            "session_id": SESSION,
        },
        systmp,
    )


def _stop(systmp: Path, **extra) -> tuple[int, str]:
    return _run(VALIDATE, {"session_id": SESSION, **extra}, systmp)


def _ledger(systmp: Path) -> Path:
    return systmp / "edit-validate" / f"{SANITISED}.edits"


# --- producer ----------------------------------------------------------------


@pytest.mark.parametrize("tool_name", ["Edit", "Write", "MultiEdit"])
def test_recorder_appends_the_edited_path(sandbox, tool_name):
    systmp, work = sandbox
    target = work / "a.py"
    rc, out = _record(systmp, str(target), tool_name)
    assert (rc, out) == (0, "")
    assert _ledger(systmp).read_text(encoding="utf-8") == f"{target}\n"


def test_recorder_sanitises_the_session_id_the_way_the_consumer_expects(sandbox):
    """The two halves reconstruct the path independently; they must agree."""
    systmp, work = sandbox
    _record(systmp, str(work / "a.py"))
    assert _ledger(systmp).exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_name": "Read", "tool_input": {"file_path": "/x.py"}},
        {"tool_name": "Edit", "tool_input": {}},
        {"tool_name": "Edit"},
        {},
    ],
)
def test_recorder_ignores_irrelevant_events(sandbox, payload):
    systmp, _ = sandbox
    payload = {"session_id": SESSION, **payload}
    rc, out = _run(RECORD, payload, systmp)
    assert (rc, out) == (0, "")
    assert not _ledger(systmp).exists()


def test_recorder_is_fail_open_on_malformed_stdin(sandbox):
    systmp, _ = sandbox
    proc = subprocess.run(
        [sys.executable, "-B", str(RECORD)],
        input="{not json",
        capture_output=True,
        text=True,
        env=_env(systmp),
        timeout=60,
    )
    assert (proc.returncode, proc.stdout) == (0, "")


# --- producer -> consumer round trip -----------------------------------------


def test_stop_blocks_on_a_file_the_recorder_flagged_as_edited(sandbox):
    systmp, work = sandbox
    broken = work / "broken.py"
    broken.write_text("def f(:\n", encoding="utf-8")
    _record(systmp, str(broken))

    rc, out = _stop(systmp)
    assert rc == 0
    assert out.strip(), "Stop did not consume the recorder's ledger"
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "broken.py" in payload["reason"]


def test_stop_is_silent_for_a_healthy_edited_file(sandbox):
    """Positive control: the block above is caused by the FILE, not by any edit."""
    systmp, work = sandbox
    healthy = work / "fine.py"
    healthy.write_text("VALUE = 1\n", encoding="utf-8")
    _record(systmp, str(healthy))
    assert _stop(systmp) == (0, "")


def test_stop_is_silent_when_the_recorder_wrote_nothing(sandbox):
    systmp, _ = sandbox
    assert _stop(systmp) == (0, "")


def test_stop_consumes_the_ledger(sandbox):
    systmp, work = sandbox
    broken = work / "broken.py"
    broken.write_text("def f(:\n", encoding="utf-8")
    _record(systmp, str(broken))
    _stop(systmp)
    assert not _ledger(systmp).exists()


def test_the_same_breakage_is_never_nudged_twice(sandbox):
    """Loop-proofness guard 2 -- dedupe by (file, error-signature)."""
    systmp, work = sandbox
    broken = work / "broken.py"
    broken.write_text("def f(:\n", encoding="utf-8")

    _record(systmp, str(broken))
    first_rc, first_out = _stop(systmp)
    assert first_out.strip()

    _record(systmp, str(broken))
    assert _stop(systmp) == (0, ""), "re-nudged the same breakage"
    assert first_rc == 0


def test_stop_never_blocks_inside_a_continuation(sandbox):
    """Loop-proofness guard 3 -- caps any chain at one extra turn."""
    systmp, work = sandbox
    broken = work / "broken.py"
    broken.write_text("def f(:\n", encoding="utf-8")
    _record(systmp, str(broken))
    assert _stop(systmp, stop_hook_active=True) == (0, "")


def test_stop_validate_off_disables_the_gate(sandbox):
    systmp, work = sandbox
    broken = work / "broken.py"
    broken.write_text("def f(:\n", encoding="utf-8")
    _record(systmp, str(broken))

    env = _env(systmp)
    env["STOP_VALIDATE"] = "off"
    proc = subprocess.run(
        [sys.executable, "-B", str(VALIDATE)],
        input=json.dumps({"session_id": SESSION}),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert (proc.returncode, proc.stdout) == (0, "")


def test_broken_json_is_reported_too(sandbox):
    systmp, work = sandbox
    bad = work / "conf.json"
    bad.write_text("{ nope", encoding="utf-8")
    _record(systmp, str(bad), tool_name="Write")
    rc, out = _stop(systmp)
    assert rc == 0
    assert "conf.json" in json.loads(out)["reason"]
