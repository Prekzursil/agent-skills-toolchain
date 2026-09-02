#!/usr/bin/env python3
"""Named probe 1: synthetic controls land at declared extremes.

Re-runs both controls independently (does not trust the receipt numbers)
then checks the artifact recorded matching values.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import agreement as A  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0010.json"
TOL = 1e-9


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0010-probe1 {msg}")
    return 1


def close(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= TOL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "SYN-0010":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:SYN-0010" not in json.dumps(doc):
        return fail("sentinel absent")
    if A.CATALOG_SENTINEL not in json.dumps(doc):
        return fail("catalog completion_sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    ident = A.run_identical_control()
    rand = A.run_random_control()
    if not ident["pass"]:
        return fail(f"identical kappa={ident['coefficient']} not at maximum")
    if not rand["pass"]:
        return fail(
            f"random kappa={rand['coefficient']} not near zero "
            f"(|{A.RANDOM_ABS_MAX}| declared before draw)"
        )

    sc = doc.get("synthetic_controls") or {}
    rec_i = (sc.get("identical") or {}).get("coefficient")
    rec_r = (sc.get("random") or {}).get("coefficient")
    if rec_i is None or rec_r is None:
        return fail("artifact missing control coefficients")
    if not close(rec_i, ident["coefficient"]):
        return fail(f"identical recorded {rec_i} live {ident['coefficient']}")
    if not close(rec_r, rand["coefficient"]):
        return fail(f"random recorded {rec_r} live {rand['coefficient']}")

    thr = sc.get("thresholds_declared_before_draw") or {}
    if thr.get("declared_before_draw") is not True:
        return fail("thresholds not declared before draw")
    if not close(thr.get("identical_min"), A.IDENTICAL_MIN):
        return fail("identical threshold drift")
    if not close(thr.get("random_abs_max"), A.RANDOM_ABS_MAX):
        return fail("random threshold drift")

    if not (sc.get("identical") or {}).get("pass"):
        return fail("artifact identical.pass is false")
    if not (sc.get("random") or {}).get("pass"):
        return fail("artifact random.pass is false")

    live = doc.get("live_panel") or {}
    live_status = str(live.get("status") or "")
    if live_status not in {"COMPUTED", "NOT-CHECKED"}:
        return fail(f"live_panel.status {live_status}")
    if live_status == "NOT-CHECKED" and doc.get("coefficient", {}).get("value") not in (None,):
        # Headline must not invent a live number when the panel is absent.
        if doc.get("coefficient", {}).get("status") != "NOT-CHECKED":
            return fail("live NOT-CHECKED but headline coefficient claimed COMPUTED")

    payload = {
        "probe": "probe1-synthetic-controls",
        "identical_kappa": ident["coefficient"],
        "random_kappa": rand["coefficient"],
        "identical_pass": ident["pass"],
        "random_pass": rand["pass"],
        "thresholds_declared_before_draw": True,
        "live_status": live_status,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"identical={ident['coefficient']} random={rand['coefficient']} "
        f"live={live_status}"
    )
    print("SUCCESS:SYN-0010-probe1 synthetic controls at expected extremes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
