#!/usr/bin/env python3
"""Named probe 2: scratch PR without sign-off vs compliant control PR."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from enforcement import run  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/adversarial/ADV-0057-governance-policy-legal-coherence.json"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0057-probe2 {msg}")
    return 1


def verify_artifact(live: dict) -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"unparseable:{exc}"
    if "SUCCESS:ADV-0057" not in text:
        return "sentinel-absent"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    ctrl = tests.get("compliant-scratch-pr")
    if not ctrl:
        return "compliant-scratch-pr-test-absent"
    if ctrl.get("result") != "PASS":
        return f"compliant-scratch-pr:{ctrl.get('result')}"
    if live.get("globally_broken_ci"):
        return "globally-broken-ci-would-be-misread-as-enforcement"
    if not live["planted_dco"]["ok"]:
        return "planted-dco-detector-uncalibrated"
    return None


def main() -> int:
    live = run()
    print(json.dumps(live, sort_keys=True))
    print(
        "unsigned_blocked={0} signed_blocked={1} unenforced={2} planted_ok={3} control_pass={4}".format(
            live["unsigned_live"]["blocked"],
            live["signed_live"]["blocked"],
            live["unenforced_signoff"],
            live["planted_dco"]["ok"],
            live["control_compliant_scratch_pr_passes"],
        )
    )
    if not live.get("pass"):
        return fail("enforcement probe did not calibrate or compliant PR failed")
    err = verify_artifact(live)
    if err:
        return fail(err)
    print("SUCCESS:ADV-0057-probe2 scratch-PR enforcement and compliant-PR control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
