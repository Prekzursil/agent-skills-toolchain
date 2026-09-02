#!/usr/bin/env python3
"""Probe 1: missing-path and size-floor known-broken; healthy set silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import controls as C  # noqa: E402
import verifier as V  # noqa: E402

ART = V.REPO / "command-center" / "receipts" / "CNF-0162.json"
UNIT = "CNF-0162"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0162-probe1 {msg}")
    return 1


def main() -> int:
    missing = C.known_broken_missing_path()
    if not missing["pass"]:
        return fail(f"missing-path not caught {json.dumps(missing, sort_keys=True)}")
    size = C.known_broken_size_floor()
    if not size["pass"]:
        return fail(f"size-floor not caught {json.dumps(size, sort_keys=True)}")
    if size["zero_bytes"] != 0 or size["one_bytes"] != 1:
        return fail(f"size controls not 0 and 1: {size}")
    healthy = C.both_states_healthy()
    if not healthy["pass"]:
        return fail(f"healthy set not silent {json.dumps(healthy, sort_keys=True)}")

    receipt_ok = None
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {st}")
        if "SUCCESS:CNF-0162" not in text:
            return fail("receipt sentinel-absent")
        tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
        for tid in (
            "known-broken-missing-path",
            "known-broken-size-floor",
            "both-states-healthy",
        ):
            if tests.get(tid, {}).get("result") != "PASS":
                return fail(f"receipt test {tid} not PASS")
        receipt_ok = True

    payload = {
        "probe": "probe1-missing-and-size-floor",
        "unit_id": UNIT,
        "missing_path_caught": True,
        "claimed_exists_not_trusted": True,
        "zero_byte_fails_floor": True,
        "one_byte_fails_floor": True,
        "healthy_silent": True,
        "healthy_n": healthy["n"],
        "floor": V.DEFAULT_MIN_BYTES,
        "receipt_checked": receipt_ok,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:CNF-0162-probe1 missing-path and 0/1-byte size floor caught; healthy silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
