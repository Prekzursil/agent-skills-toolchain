#!/usr/bin/env python3
"""Probe 2: concurrent atomic append (no tear) + reorder + planted interleave."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from paths import CATALOG_SENTINEL, OUT_REL, REPO, UNIT  # noqa: E402
from suite import (  # noqa: E402
    concurrent_atomic,
    concurrent_naive_or_planted,
    reorder_control,
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    atomic = concurrent_atomic(8)
    if atomic.get("torn"):
        return fail(f"atomic concurrent torn {atomic}")
    if not atomic.get("pass") or not atomic.get("ok"):
        return fail(f"atomic concurrent {atomic}")
    if atomic.get("parsed_ok", 0) < 2:
        return fail("atomic concurrent under-parsed")

    reorder = reorder_control()
    if not reorder.get("pass") or not reorder.get("fired_on_bad"):
        return fail(f"reorder {reorder}")
    if not reorder.get("silent_on_good"):
        return fail("reorder not silent on good")

    interleave = concurrent_naive_or_planted()
    if not interleave.get("pass") or not interleave.get("planted_fired"):
        return fail(f"interleave control {interleave}")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in ("concurrent-no-tear", "reorder-detected", "planted-interleave-fires"):
        if tests.get(tid, {}).get("result") != "PASS":
            return fail(f"artifact test {tid} not PASS")

    ncs = doc.get("negative_controls") or []
    if not any(
        x.get("id") == "reorder-prior-events" and x.get("fired_on_bad_state") for x in ncs
    ):
        return fail("receipt missing reorder negative control")
    if not any(
        x.get("id") == "planted-interleave" and x.get("fired_on_bad_state") for x in ncs
    ):
        return fail("receipt missing planted-interleave negative control")

    evidence = doc.get("evidence") or []
    if not any(
        e.get("verdict") == "CONFIRMED"
        and "concurrent" in str(e.get("claim") or "").lower()
        for e in evidence
        if isinstance(e, dict)
    ):
        return fail("receipt missing CONFIRMED concurrent evidence")

    out = {
        "probe": "probe2-concurrent-and-reorder",
        "unit_id": UNIT,
        "atomic_torn": False,
        "atomic_parsed_ok": atomic.get("parsed_ok"),
        "lost_updates_possible": atomic.get("lost_updates_possible"),
        "reorder_fired": True,
        "planted_interleave_fired": True,
        "naive_torn_hits": interleave.get("naive_torn_hits"),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"atomic_torn=False parsed_ok={atomic.get('parsed_ok')} "
        f"reorder_fired=True planted_fired=True "
        f"naive_torn={interleave.get('naive_torn_hits')}/{interleave.get('naive_trials')}"
    )
    print(f"SUCCESS:{UNIT}-probe2 concurrent+reorder both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
