#!/usr/bin/env python3
"""Probe 2: detector control — plant a step that cannot run.

Catalog test: add a step that cannot run and confirm it appears in the
unexecuted list.

Both-states:
  good  = unmodified workflow does not list planted-cannot-run
  bad   = after planting `if: ${{ false }}`, the detector lists it as
          unexecuted with skip_reason=conditional_false
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "TST-0332"
ART = REPO / "command-center/receipts/TST-0332.json"
WF = HERE / "fixtures/workflows/phase0-ci-test-gap.yml"
RUN = HERE / "fixtures/runs/latest-green.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def check_receipt(ctl: dict) -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {doc.get('state')}"
    if "SUCCESS:TST-0332" not in text:
        return "sentinel-absent"
    nc = doc.get("negative_control") or {}
    if nc.get("fired_on_bad_state") is not True:
        return "receipt control did not fire on planted cannot-run"
    if nc.get("silent_on_good_state") is not True:
        return "receipt control not silent on unmodified workflow"
    if nc.get("planted_name") != H.PLANTED_NAME:
        return f"receipt planted_name {nc.get('planted_name')}"
    if not ctl.get("ok"):
        return "live control not ok"
    return None


def main() -> int:
    H.write_fixtures(HERE)
    tmp = Path(tempfile.mkdtemp(prefix="tst0332-p2-"))
    try:
        ctl = H.detector_control(WF, RUN, tmp)
        print(f"planted_name={ctl['planted_name']}")
        print(f"before_declared={ctl['before_declared']}")
        print(f"after_declared={ctl['after_declared']}")
        print(f"before_had_planted={ctl['before_had_planted']}")
        print(f"fired_on_bad_state={ctl['fired_on_bad_state']}")
        print(f"silent_on_good_state={ctl['silent_on_good_state']}")
        print(f"after_unexecuted={ctl['after_unexecuted']}")
        if ctl["before_had_planted"]:
            return fail("planted step already present in the unmodified workflow")
        if ctl["after_declared"] != ctl["before_declared"] + 1:
            return fail("plant did not add exactly one declared test step")
        if not ctl["fired_on_bad_state"]:
            return fail("planted cannot-run step missing from unexecuted list")
        if not ctl["silent_on_good_state"]:
            return fail("control fired on the unmodified workflow")
        row = ctl["after_unexecuted"][0]
        if row.get("skip_reason") != "conditional_false":
            return fail(f"planted skip_reason {row.get('skip_reason')}")
        if not ctl["ok"]:
            return fail("detector_control.ok is false")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    err = check_receipt(ctl)
    if err:
        return fail(err)

    print(
        json.dumps(
            {
                "probe": "probe2-cannot-run-control",
                "unit_id": UNIT,
                "planted_name": H.PLANTED_NAME,
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "skip_reason": "conditional_false",
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:TST-0332-probe2 planted-cannot-run appears unexecuted "
        "with skip_reason=conditional_false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
