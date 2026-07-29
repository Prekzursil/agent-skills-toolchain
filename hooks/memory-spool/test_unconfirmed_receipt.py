#!/usr/bin/env python3
"""memory-spool must not report an ABSENT receipt as a CONFIRMED failure.

``rules/common/single-signal-verification.md`` (§1, §4) forbids concluding
FAILED from one signal: "Absence/failure needs corroboration ... 'Nothing
there', 'it crashed', 'it's done' -- each is a claim, not an observation."

``_common.response_ok`` deliberately answers ONE question -- "may I drop the
spool?" -- and correctly folds every uncertain shape into ``False`` so an
unconfirmed write is never silently discarded.  That bias is right and is not
what these tests target.  What ``flush_check`` then did with that ``False`` was
wrong: it wrote ``status="failed"`` and told the agent "Memory is NOT
persisted" for a *missing* receipt exactly as for an explicit error envelope.
The store may well have committed the note and only the transport dropped the
result, so the categorical claim can be false, and acting on the emitted
"re-attempt the write" advice can DUPLICATE an already-landed non-idempotent
``edit_note`` append/prepend.

These tests pin the distinction: an explicit error envelope keeps the loud
CONFIRMED-failure wording, an absent/empty receipt is reported as UNCONFIRMED
and steers to a read-back instead of a blind re-attempt.  Both arms are
asserted so a future change cannot fix one by breaking the other.

Runs under ``pytest hooks/`` (quality.yml). The sibling ``test_memory_spool.py``
defines no ``test_*`` function, so pytest collects ZERO tests from it -- these
assertions would never execute if they were added there.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

THIS = Path(__file__).resolve().parent


def _load_isolated():
    """Load THIS dir's ``_common`` + ``flush_check``, immune to a sibling's ``_common``.

    Six hook dirs ship a DIFFERENT ``_common.py`` under the one flat
    ``sys.modules`` key, so collection order otherwise decides which one
    ``flush_check`` binds (see ``test_replay.py`` for the measured failure).
    """
    prev = sys.modules.get("_common")
    had_prev = "_common" in sys.modules
    try:
        cspec = importlib.util.spec_from_file_location("_common", THIS / "_common.py")
        common = importlib.util.module_from_spec(cspec)
        sys.modules["_common"] = common
        cspec.loader.exec_module(common)

        fspec = importlib.util.spec_from_file_location(
            "memory_spool_flush_under_test", THIS / "flush_check.py"
        )
        flush = importlib.util.module_from_spec(fspec)
        sys.modules[fspec.name] = flush
        fspec.loader.exec_module(flush)
    finally:
        if had_prev:
            sys.modules["_common"] = prev
        else:
            sys.modules.pop("_common", None)
    return common, flush


C, flush_check = _load_isolated()

assert flush_check.C is C, "flush_check bound a sibling hook's _common"

_TOOL = "mcp__basic-memory__write_note"
_TITLE = "Alpha decision"


def _fresh_spool_dir() -> Path:
    """Point the isolated ``_common`` at an empty per-test spool dir."""
    tmp = Path(tempfile.mkdtemp(prefix="memspool-unconfirmed-"))
    C.SPOOL_DIR = tmp
    C.REPORTED_FILE = tmp / ".reported.json"
    return tmp


def _payload(response) -> dict:
    return {
        "tool_name": _TOOL,
        "tool_input": {"title": _TITLE, "content": "body"},
        "tool_response": response,
    }


def _spool_one() -> Path:
    """Write one pending spool record through ``_common``'s OWN writer.

    Deliberately not a hand-rolled path: ``find_spools`` globs
    ``*-<key>.json`` (``spool_path`` prefixes ``int(ts)``), so a file named
    ``<key>.json`` is invisible to the hook and every assertion below would
    "fail" against a spool the code never saw -- a broken detector, not a
    finding. Measured: that mistake produced 7/7 red including the two arms
    that must be GREEN on unfixed code.
    """
    ti = {"title": _TITLE, "content": "body"}
    rec = {
        "ts": C.now(),
        "tool": _TOOL,
        "title": _TITLE,
        "payload": ti,
        "key": C.payload_key(_TOOL, ti),
        "status": "pending",
    }
    path = C.write_spool(rec)
    assert path is not None and path.is_file(), "fixture spool was not written"
    assert C.find_spools(rec["key"]) == [path], (
        "fixture is invisible to find_spools -- the detector, not the hook, is broken"
    )
    return path


def _run_posttool(response) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = flush_check.run_posttool(_payload(response))
    assert rc == 0, "the hook is inject-only and must always exit 0"
    return buf.getvalue()


def _emitted(out: str) -> str:
    if not out.strip():
        return ""
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


# --- ARM 1: an EXPLICIT error envelope -> the loud CONFIRMED-failure wording ----


def test_explicit_error_envelope_still_reports_a_confirmed_failure():
    _fresh_spool_dir()
    kept = _spool_one()
    msg = _emitted(
        _run_posttool(
            {
                "isError": True,
                "content": [{"type": "text", "text": "basic-memory not connected"}],
            }
        )
    )
    assert msg, "an explicit error must still alert"
    assert "NOT persisted" in msg, (
        "a store that reported an error IS a confirmed failure -- do not soften it"
    )
    assert json.loads(kept.read_text(encoding="utf-8"))["status"] == "failed"


# --- ARM 2: an ABSENT/EMPTY receipt -> UNCONFIRMED, never a failure claim ------


def test_absent_receipt_is_recorded_as_unconfirmed_not_failed():
    """The spool is still kept -- only the VERDICT written onto it changes."""
    _fresh_spool_dir()
    kept = _spool_one()
    _run_posttool(None)
    assert kept.exists(), "an unconfirmed write must still keep its spool"
    assert json.loads(kept.read_text(encoding="utf-8"))["status"] == "unconfirmed", (
        "no receipt observed is not the same observation as the store reporting "
        "an error; single-signal-verification.md forbids collapsing them"
    )


def test_absent_receipt_message_makes_no_categorical_persistence_claim():
    _fresh_spool_dir()
    _spool_one()
    msg = _emitted(_run_posttool(None))
    assert msg, "an unconfirmed write must still be surfaced"
    assert "NOT persisted" not in msg, (
        "the hook only observed a missing receipt; it has not established that "
        "the write did not land"
    )
    assert "UNCONFIRMED" in msg.upper()


def test_absent_receipt_steers_to_readback_before_a_blind_reattempt():
    """Re-attempting a non-idempotent ``edit_note`` can duplicate a landed edit."""
    _fresh_spool_dir()
    _spool_one()
    msg = _emitted(_run_posttool(None)).lower()
    assert "read" in msg, "must ask for an independent read-back as the second signal"


def test_empty_shapes_take_the_unconfirmed_path_too():
    """``response_ok`` returns False for each of these; none is an error report."""
    for empty in ("", {}, []):
        _fresh_spool_dir()
        kept = _spool_one()
        msg = _emitted(_run_posttool(empty))
        status = json.loads(kept.read_text(encoding="utf-8"))["status"]
        assert status == "unconfirmed", f"{empty!r} -> {status!r}"
        assert "NOT persisted" not in msg, f"{empty!r} produced a failure claim"


def test_success_receipt_still_clears_the_spool_silently():
    """Control: the fix must not disturb the confirmed-success path."""
    _fresh_spool_dir()
    kept = _spool_one()
    out = _run_posttool(
        {"isError": False, "content": [{"type": "text", "text": "permalink: notes/x"}]}
    )
    assert not out.strip(), "a confirmed save must stay silent"
    assert not kept.exists(), "a confirmed save must clear the spool"


# --- the SessionStart replay wording rests on the same single signal ----------


def test_sessionstart_does_not_claim_unconfirmed_entries_were_lost():
    _fresh_spool_dir()
    _spool_one()
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = flush_check.run_sessionstart({})
    assert rc == 0
    msg = _emitted(buf.getvalue())
    assert msg, "unflushed entries must still be surfaced once"
    assert "lost mid-write" not in msg, (
        "'never confirmed saved' is the observation; 'lost mid-write' is an "
        "unevidenced conclusion about what happened in the store"
    )
