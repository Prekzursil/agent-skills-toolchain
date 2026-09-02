#!/usr/bin/env python3
"""Probe 1: known-divergent UP051 control + pin fidelity (ruff --version)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
import toolchain as T  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0185.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0185-probe1 {msg}")
    return 1


def main() -> int:
    live = S.run_matrix()
    claim = next(
        c
        for c in live["claims"]
        if c["id"] == "ruff-check-UP-preview-abstractclassmethod"
    )
    pin_inv, pin_out = T.ruff_version_stdout(T.RUFF_PIN)
    print(
        json.dumps(
            {
                "probe": "probe1-divergent-pin",
                "claim_id": claim["id"],
                "verdict_ci_pin": claim["verdict_ci_pin"],
                "verdict_comparison": claim["verdict_comparison"],
                "version_sensitive": claim["version_sensitive"],
                "pin_invocation": pin_inv,
                "pin_version_stdout": pin_out,
                "pin_matches": T.RUFF_PIN in pin_out,
                "ambient_path_unused": True,
            },
            sort_keys=True,
        )
    )
    if claim["verdict_ci_pin"] != "PASS":
        return fail(f"known-divergent pin side not PASS: {claim['verdict_ci_pin']}")
    if claim["verdict_comparison"] != "FAIL":
        return fail(
            f"known-divergent 0.15.22 side not FAIL: {claim['verdict_comparison']}"
        )
    if T.RUFF_PIN not in pin_out:
        return fail(f"pin fidelity: version stdout {pin_out!r} missing {T.RUFF_PIN}")
    if T.RUFF_PIN not in pin_inv:
        return fail(f"pin invocation not version-qualified: {pin_inv}")
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CNF-0185" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    pf = S.domain_get(doc, "pin_fidelity") or {}
    if not isinstance(pf, dict) or pf.get("matches_pin") is not True:
        return fail("artifact pin_fidelity.matches_pin is not true")
    if T.RUFF_PIN not in str(pf.get("version_stdout") or ""):
        return fail("artifact version_stdout does not cite pinned ruff")
    vs = S.domain_get(doc, "version_sensitive_set") or []
    if not isinstance(vs, list):
        vs = []
    if not any(x.get("id") == claim["id"] for x in vs if isinstance(x, dict)):
        return fail("artifact version_sensitive_set missing UP051 claim")
    print(
        "divergent pin=PASS comparison=FAIL pin_version="
        + pin_out
        + " invocation="
        + pin_inv
    )
    print("SUCCESS:CNF-0185-probe1 known-divergent control and pin fidelity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
