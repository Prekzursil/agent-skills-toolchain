#!/usr/bin/env python3
"""Probe 1: identical-command confirmation is rejected.

Also re-runs the paired shell-axis control in the SAME invocation so the
two fingerprint controls return opposite verdicts as designed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fingerprint as F  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0006-probe-independence.json"


def ensure_artifact() -> int:
    if ART.is_file() and ART.stat().st_size > 0:
        return 0
    import emit_audit as E  # noqa: WPS433

    return int(E.main())


def main() -> int:
    rc = ensure_artifact()
    if rc != 0:
        print("FAILED:CNF-0006-probe1 emit failed")
        return rc
    controls = F.run_fingerprint_controls()
    ident = controls["identical_command"]
    shell = controls["shell_only"]
    print(
        "identical_verdict={0} identical_class={1} pass={2}".format(
            ident["observed_verdict"], ident["classification"], ident["pass"]
        )
    )
    print(
        "shell_verdict={0} shell_class={1} axes={2} pass={3}".format(
            shell["observed_verdict"],
            shell["classification"],
            shell["differing_axes"],
            shell["pass"],
        )
    )
    print(
        "same_invocation={0} opposite={1}".format(
            controls["same_invocation"], controls["opposite_verdicts_as_designed"]
        )
    )
    if not ident["pass"]:
        print("FAILED:CNF-0006-probe1 identical command was not rejected")
        return 1
    if not controls["opposite_verdicts_as_designed"]:
        print("FAILED:CNF-0006-probe1 controls did not return opposite verdicts")
        return 1
    if ident["observed_verdict"] == shell["observed_verdict"]:
        print("FAILED:CNF-0006-probe1 detector-failure identical and shell agreed")
        return 1

    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0006-probe1 self-declared {doc.get('state')}")
        return 1
    body = F.report_body(doc)
    recorded = {row["id"]: row for row in body.get("controls") or [] if isinstance(row, dict)}
    rec_ident = recorded.get("control-identical-command-reject") or {}
    if rec_ident.get("observed_verdict") != "REJECTED" or rec_ident.get("pass") is not True:
        print("FAILED:CNF-0006-probe1 artifact did not record identical REJECTED")
        return 1
    if not body.get("controls_same_invocation"):
        print("FAILED:CNF-0006-probe1 artifact missing same-invocation flag")
        return 1
    print("SUCCESS:CNF-0006-probe1 identical-command rejected; opposite shell control in same invocation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
