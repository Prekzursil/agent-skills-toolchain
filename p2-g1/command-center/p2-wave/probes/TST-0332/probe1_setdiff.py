#!/usr/bin/env python3
"""Probe 1: set difference declared vs executed + skip-reason attribution.

Catalog tests:
  * Set difference between declared and executed steps for the latest green run.
  * Skip-reason attribution per unexecuted step (conditional false, matrix
    exclusion, earlier failure, cancelled).

A green badge with unexecuted steps is required — that is the false green
the unit exists to make visible.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import reviewer as R  # noqa: E402

UNIT = "TST-0332"
ART = REPO / "command-center/receipts/TST-0332.json"
WF = HERE / "fixtures/workflows/phase0-ci-test-gap.yml"
RUN = HERE / "fixtures/runs/latest-green.json"
LOG = HERE / "fixtures/runs/latest-green.log"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def check_receipt(live: dict) -> str | None:
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
    gap = doc.get("declared_executed_gap") or {}
    if gap.get("declared_count") != live["declared_count"]:
        return f"receipt declared_count {gap.get('declared_count')} != live {live['declared_count']}"
    if gap.get("executed_count") != live["executed_count"]:
        return f"receipt executed_count {gap.get('executed_count')} != live"
    if gap.get("unexecuted_count") != live["unexecuted_count"]:
        return f"receipt unexecuted_count {gap.get('unexecuted_count')} != live"
    rec_unex = {
        (r.get("job"), r.get("name"), r.get("matrix_key") or "", r.get("skip_reason"))
        for r in (gap.get("unexecuted") or [])
        if isinstance(r, dict)
    }
    live_unex = {
        (r["job"], r["name"], r.get("matrix_key") or "", r["skip_reason"])
        for r in live["unexecuted"]
    }
    if rec_unex != live_unex:
        return "receipt unexecuted list drifted from live harness"
    if gap.get("green_badge") is not True:
        return "receipt did not record a green badge"
    if gap.get("gap_invisible_from_badge") is not True:
        return "receipt missed the green-not-live finding"
    return None


def main() -> int:
    H.write_fixtures(HERE)
    if not WF.is_file() or not RUN.is_file() or not LOG.is_file():
        return fail("phase0 fixtures missing after write")
    live = H.analyze(WF, RUN, LOG)
    rev = R.review(WF, RUN, LOG)

    print(f"declared_count={live['declared_count']}")
    print(f"executed_count={live['executed_count']}")
    print(f"unexecuted_count={live['unexecuted_count']}")
    print(f"skip_reasons={live['skip_reasons_present']}")
    print(f"green_badge={live['green_badge']}")
    print(f"gap_invisible_from_badge={live['gap_invisible_from_badge']}")
    print(f"reviewer_verdict={rev['verdict']} independent={rev['independent']}")

    if live["declared_count"] != 60:
        return fail(f"declared_count {live['declared_count']} want 60")
    if live["executed_count"] != 28:
        return fail(f"executed_count {live['executed_count']} want 28")
    if live["unexecuted_count"] != 32:
        return fail(f"unexecuted_count {live['unexecuted_count']} want 32")
    if live["declared_count"] != live["executed_count"] + live["unexecuted_count"]:
        return fail("declared != executed + unexecuted")
    if live["unexecuted_missing_reason"]:
        return fail(f"unexecuted missing skip_reason {live['unexecuted_missing_reason'][:5]}")
    missing_kinds = set(H.SKIP_REASONS) - set(live["skip_reasons_present"])
    if missing_kinds:
        return fail(f"skip-reason kinds missing {sorted(missing_kinds)}")
    if not live["green_badge"]:
        return fail("fixture run is not green")
    if not live["gap_invisible_from_badge"]:
        return fail("green badge hid no gap — detector vacuous")
    if live["naive_green_implies_all_executed"] is not True:
        return fail("naive badge inference should still claim all-executed")
    if live["naive_green_implies_all_executed"] and live["unexecuted_count"] == 0:
        return fail("naive inference accidentally true")

    by_reason = {k: 0 for k in H.SKIP_REASONS}
    for row in live["unexecuted"]:
        by_reason[row["skip_reason"]] += 1
        if not row.get("name") or not row.get("job"):
            return fail(f"unexecuted row missing name/job {row}")
    print(f"unexecuted_by_reason={by_reason}")
    for kind, n in by_reason.items():
        if n < 1:
            return fail(f"no unexecuted step with skip_reason={kind}")

    log_names = H.parse_log_executed(LOG)
    exec_names = {r["name"] for r in live["executed"]}
    if log_names != exec_names:
        return fail(
            f"text log executed {sorted(log_names)[:3]} != harness {sorted(exec_names)[:3]}"
        )

    if rev["saw_conclusion_first"] is not False:
        return fail("reviewer was anchored on a conclusion")
    if rev["independent"] is not True:
        return fail("reviewer not independent")
    if rev["declared_count"] != live["declared_count"]:
        return fail(f"reviewer declared {rev['declared_count']} != harness")
    if rev["executed_count"] != live["executed_count"]:
        return fail("reviewer executed drifted")
    if rev["unexecuted_count"] != live["unexecuted_count"]:
        return fail("reviewer unexecuted drifted")
    rev_unex = {
        (r["job"], r["name"], r.get("matrix_key") or "", r["skip_reason"])
        for r in rev["unexecuted"]
    }
    live_unex = {
        (r["job"], r["name"], r.get("matrix_key") or "", r["skip_reason"])
        for r in live["unexecuted"]
    }
    if rev_unex != live_unex:
        return fail("independent skip-reason derivation != harness")
    if rev["verdict"] != "PASS":
        return fail(f"reviewer verdict {rev['verdict']}")

    src = H.live_sources(REPO)
    wf_present = (REPO / ".github" / "workflows").is_dir()
    if bool(src.get("workflows_dir")) != wf_present:
        return fail("live_sources.workflows_dir disagrees with disk")
    if bool(src.get("test_registry")) != (REPO / "command-center/TEST-REGISTRY.json").is_file():
        return fail("live_sources.test_registry disagrees with disk")
    if bool(src.get("gh_cli")) != (shutil.which("gh") is not None):
        return fail("live_sources.gh_cli disagrees with shutil.which")
    notes = str(src.get("notes") or "").lower()
    if wf_present and "no .github/workflows" in notes:
        return fail("live_sources notes claim workflows absent while they exist")
    live_q = src.get("live_quality") or {}
    if wf_present and (REPO / ".github/workflows/quality.yml").is_file():
        if int(live_q.get("declared_count") or 0) < 1:
            return fail("live quality.yml present but declared_count is 0")

    err = check_receipt(live)
    if err:
        return fail(err)

    print(
        json.dumps(
            {
                "probe": "probe1-setdiff-skip-reasons",
                "unit_id": UNIT,
                "declared_count": live["declared_count"],
                "executed_count": live["executed_count"],
                "unexecuted_count": live["unexecuted_count"],
                "unexecuted_by_reason": by_reason,
                "green_badge": True,
                "gap_invisible_from_badge": True,
                "reviewer_agrees": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:TST-0332-probe1 declared=60 executed=28 unexecuted=32 "
        "with all four skip reasons on a green run"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
