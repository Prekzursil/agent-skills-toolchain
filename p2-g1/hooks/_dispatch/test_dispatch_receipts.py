#!/usr/bin/env python3
"""Dispatcher FLIGHT-ATTESTATION regression tests (C33 D-l02, re-derived).

``run()`` catches a matched check's import failure and continues, returns ``None``
when nothing loaded, and drops timed-out checks — all with no output at all.
Measured before this suite: a Stop event whose one matched check could not load,
and a Stop event where NO check was selected, both produced ``(None, "")`` on
every observable channel.  Direct checker success plus static registration
therefore never attested that the dispatcher actually selected, loaded, ran and
delivered anything.

SCOPE, stated so it is not overclaimed: this is dispatcher-side OBSERVABILITY.
It is NOT a nonce/ledger receipt and does NOT prove the Claude host invoked and
delivered the hook — that needs a live Stop canary on the Windows host. What it
closes is the dispatcher-side indistinguishability above.

The sibling loss — a check's non-zero (block) return being discarded — is already
attested by ``dispatch.py``'s ``_disarmed_note`` and covered in
``test_dispatch_runtime.py``; this suite deliberately does not duplicate it.

Run: pytest hooks/_dispatch/test_dispatch_receipts.py -q
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_dispatch():
    """Fresh copy of dispatch.py (bypasses the import cache)."""
    spec = importlib.util.spec_from_file_location("dispatch_mod", HERE / "dispatch.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifest(checks: list[dict], root: str, event: str = "Stop") -> dict:
    return {"version": 1, "hooks_root": root, "events": {event: {"checks": checks}}}


def _dispatch_run(mod, event, payload, manifest):
    """Call ``run()`` with the same per-thread stdout/stdin routing ``main()`` installs.

    Without the proxies a check's ``print`` escapes to the real stdout instead of its
    private buffer, so the aggregate reads empty — an artifact of the harness, not of
    the dispatcher.
    """
    old_out, old_in = sys.stdout, sys.stdin
    sys.stdout = mod._ThreadStdout(old_out)
    sys.stdin = mod._ThreadStdin(old_in)
    try:
        return mod.run(event, json.dumps(payload), manifest)
    finally:
        sys.stdout, sys.stdin = old_out, old_in


def _run_capturing_stderr(mod, event, payload, manifest):
    old_err = sys.stderr
    cap = io.StringIO()
    sys.stderr = cap
    try:
        out = _dispatch_run(mod, event, payload, manifest)
    finally:
        sys.stderr = old_err
    return out, cap.getvalue()


# --------------------------------------------------------------------------- #
# 1. flight receipts
# --------------------------------------------------------------------------- #
def test_matched_check_that_cannot_load_emits_a_receipt(tmp_path):
    """A matched-but-unloadable check must NOT look like a healthy quiet event."""
    mod = load_dispatch()
    manifest = _manifest(
        [{"name": "ghost/check", "script": "ghost/check.py", "timeout": 5}],
        str(tmp_path),
    )
    out, err = _run_capturing_stderr(mod, "Stop", {}, manifest)
    assert out is None, "nothing loaded -> no aggregated context (unchanged, fail-open)"
    assert mod.RECEIPT_PREFIX in err, "the non-delivery must be attested on stderr"
    assert "check=ghost/check" in err
    assert "status=load-failed" in err
    assert "event=Stop" in err


def test_no_selected_check_is_silent(tmp_path):
    """CONTROL — the healthy quiet event must stay completely silent.

    This is the state the failure above used to be byte-identical to; if this
    control ever starts printing, the receipt has become noise instead of signal.
    """
    mod = load_dispatch()
    manifest = _manifest(
        [{"name": "x", "script": "x.py", "timeout": 5, "matcher": "NeverMatches"}],
        str(tmp_path),
    )
    out, err = _run_capturing_stderr(mod, "Stop", {"tool_name": "Read"}, manifest)
    assert out is None
    assert err == "", "a healthy event with no selected check must emit nothing"


def test_receipt_distinguishes_the_two_states(tmp_path):
    """The whole point: the two states must now be observationally DIFFERENT."""
    mod = load_dispatch()
    broken = _manifest(
        [{"name": "ghost", "script": "ghost/check.py", "timeout": 5}], str(tmp_path)
    )
    healthy = _manifest(
        [{"name": "ghost", "script": "ghost/check.py", "timeout": 5, "matcher": "Zzz"}],
        str(tmp_path),
    )
    _, err_broken = _run_capturing_stderr(mod, "Stop", {}, broken)
    _, err_healthy = _run_capturing_stderr(mod, "Stop", {"tool_name": "Read"}, healthy)
    assert err_broken != err_healthy


def test_timed_out_check_emits_a_timeout_receipt(tmp_path):
    """A check that blows its deadline is dropped fail-open — but attested."""
    hook_dir = tmp_path / "slowpoke"
    hook_dir.mkdir()
    (hook_dir / "check.py").write_text(
        "import time\n\n\ndef main():\n    time.sleep(30)\n    return 0\n",
        encoding="utf-8",
    )
    mod = load_dispatch()
    manifest = _manifest(
        [{"name": "slowpoke", "script": "slowpoke/check.py", "timeout": 0.2}],
        str(tmp_path),
    )
    out, err = _run_capturing_stderr(mod, "Stop", {}, manifest)
    assert out is None
    assert "status=timeout" in err
    assert "check=slowpoke" in err


def test_receipt_never_raises_when_stderr_is_broken(tmp_path):
    """Attestation is fail-open: a dead stderr must not break the dispatch."""
    mod = load_dispatch()

    class _Exploding:
        def write(self, _s):
            raise OSError("stderr is gone")

        def flush(self):
            raise OSError("stderr is gone")

    old_err = sys.stderr
    sys.stderr = _Exploding()
    try:
        mod._receipt("Stop", "x", "load-failed")  # must not raise
    finally:
        sys.stderr = old_err
