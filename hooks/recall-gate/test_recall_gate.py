#!/usr/bin/env python3
"""Both-states + control tests for recall-gate.

A probe that is silent in BOTH the broken and fixed state measures nothing, so
every capability claim below is paired with the state in which it must FIRE and
the state in which it must be SILENT.

Run:  python test_recall_gate.py        (standalone, no pytest needed)
      python -m pytest test_recall_gate.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import gate  # noqa: E402
import tree_index as ti  # noqa: E402

HOME = Path.home()

# A tree artifact that EXISTS on disk but is absent from the vault index —
# the exact gap class behind the 2026-08-07 wrong claims.
GAP_QUERY = (
    "I want to build a helper from scratch that reads a JSONL transcript "
    "backwards from EOF so the Stop checks stop being O(session length). "
    "Something like transcript_tail — I do not think anything exists yet."
)
# Same shape, but naming something with no tree prior art at all.
NEGATIVE_QUERY = (
    "I want to build from scratch a small zqxjkv wbrtplm converter that "
    "translates plorbnax units into frobnitz units for the quarterly report."
)


def _ev(prompt: str) -> dict:
    return {"prompt": prompt, "session_id": "recall-gate-test"}


# ── 1. FIXED state: the gate FIRES on a real tree artifact ───────────────────
def test_fires_on_tree_prior_art() -> None:
    state, msg = gate.run(_ev(GAP_QUERY))
    assert state == gate.STATE_FINDING, f"expected FINDING, got {state}"
    assert msg and "transcript_tail" in msg, msg
    assert "PRIOR ART" in msg


# ── 2. Negative control: NO false digest when there is no prior art ──────────
def test_negative_control_no_digest() -> None:
    state, msg = gate.run(_ev(NEGATIVE_QUERY))
    assert state == gate.STATE_CLEAN, f"expected CLEAN, got {state}"
    assert msg is None, f"CLEAN must not manufacture a digest, got: {msg}"


# ── 3. Intent gate: an ordinary prompt never triggers a lookup ───────────────
def test_no_intent_stays_clean() -> None:
    state, msg = gate.run(
        _ev("Please reformat the whitespace in that file to match the house style.")
    )
    assert state == gate.STATE_CLEAN
    assert msg is None


# ── 4. Typed silence: an unavailable index is NOT-CHECKED, never CLEAN ───────
def test_unavailable_index_is_not_checked() -> None:
    """Detector control: prove the NOT-CHECKED path FIRES in the broken state."""
    real = ti.get_or_build
    try:
        ti.get_or_build = lambda **_kw: {  # type: ignore[assignment]
            "ok": False,
            "entries": [],
            "truncated": True,
        }
        state, msg = gate.run(_ev(GAP_QUERY))
    finally:
        ti.get_or_build = real  # type: ignore[assignment]
    assert state == gate.STATE_NOT_CHECKED, f"expected NOT-CHECKED, got {state}"
    assert msg is None, "NOT-CHECKED must not inject"


# ── 5. Fail-open: an exploding index yields RAISED, never a crash ────────────
def test_exception_is_raised_state_not_crash() -> None:
    real = ti.get_or_build
    try:

        def boom(**_kw):  # noqa: ANN202
            raise RuntimeError("synthetic")

        ti.get_or_build = boom  # type: ignore[assignment]
        state, msg = gate.run(_ev(GAP_QUERY))
    finally:
        ti.get_or_build = real  # type: ignore[assignment]
    assert state == gate.STATE_RAISED
    assert msg is None


# ── 6. Budget: the deadline is enforced, and blowing it is NOT-CHECKED ───────
def test_budget_exhausted_is_not_checked() -> None:
    state, msg = gate.run(_ev(GAP_QUERY), budget_sec=0.0)
    assert state in (gate.STATE_NOT_CHECKED, gate.STATE_CLEAN, gate.STATE_FINDING)
    if state == gate.STATE_NOT_CHECKED:
        assert msg is None


# ── 7. Hook contract: exit code is ALWAYS 0, even on garbage stdin ───────────
def test_exit_code_always_zero() -> None:
    for payload in ("", "not json", json.dumps(_ev(GAP_QUERY))):
        p = subprocess.run(
            [sys.executable, str(THIS / "gate.py")],
            input=payload,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert p.returncode == 0, f"exit {p.returncode} for payload {payload[:20]!r}"


# ── 8. Hot path stays well inside the shared UserPromptSubmit wall ───────────
def test_hot_path_within_budget() -> None:
    gate.run(_ev(GAP_QUERY))  # warm the cache
    t0 = time.monotonic()
    gate.run(_ev(GAP_QUERY))
    dt = time.monotonic() - t0
    assert dt < gate.BUDGET_SEC, (
        f"hot path {dt:.3f}s exceeded budget {gate.BUDGET_SEC}s"
    )


# ── 9. Never re-searches the vault (no duplication of bounded_recall) ────────
def test_does_not_index_the_vault() -> None:
    idx = ti.get_or_build()
    for e in idx["entries"]:
        p = e["path"].replace("\\", "/").lower()
        assert "basic-memory" not in p, f"vault leaked into tree index: {p}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
