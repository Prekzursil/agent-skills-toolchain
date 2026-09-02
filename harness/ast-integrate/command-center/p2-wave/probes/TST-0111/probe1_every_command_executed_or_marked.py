#!/usr/bin/env python3
"""Probe 1: every fenced command is executed or explicitly marked NOT-EXECUTABLE."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import checker as K  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0111.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0111-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = K.check_artifact(doc)
    print(f"artifact_ok={ok} {why}")
    if not ok:
        print("FAILED:TST-0111-probe1 checker")
        return 1

    live = H.run_live(REPO)
    summary = live["summary"]
    files = live["corpus"].get("files") or []
    print(
        "live extracted={0} broken={1} coverage_ok={2} runner_complete={3} files={4}".format(
            summary["extracted"],
            summary["broken"],
            summary["coverage_ok"],
            summary.get("runner_complete"),
            len(files),
        )
    )
    if not files:
        print("FAILED:TST-0111-probe1 live corpus empty (green-not-live)")
        return 1
    if summary.get("runner_complete") is not True:
        print("FAILED:TST-0111-probe1 runner silently omitted a command")
        print(json.dumps(live["table"], indent=2)[:3000])
        return 1

    doc_ids = [str(r.get("id")) for r in (doc.get("execution_table") or [])]
    live_ids = [str(r.get("id")) for r in live["table"]]
    if doc_ids != live_ids:
        print(f"FAILED:TST-0111-probe1 stale table doc={doc_ids} live={live_ids}")
        return 1
    doc_sum = doc.get("summary") or {}
    if "extracted" not in doc_sum or int(doc_sum["extracted"]) != summary["extracted"]:
        print("FAILED:TST-0111-probe1 extracted drift")
        return 1
    if "broken" not in doc_sum or int(doc_sum["broken"]) != summary["broken"]:
        print("FAILED:TST-0111-probe1 broken drift")
        return 1

    controls = H.run_controls()
    print(
        "good_coverage={0} echo_ok={1} false_nonzero={2} sudo_not_executed={3}".format(
            controls["good_coverage"],
            controls["echo_ok"],
            controls["false_executed_nonzero"],
            controls["sudo_not_executed"],
        )
    )
    if not controls["good_coverage"]:
        print("FAILED:TST-0111-probe1 good fixture coverage")
        return 1
    if not controls["echo_ok"]:
        print("FAILED:TST-0111-probe1 echo did not exit 0")
        return 1
    if not controls["false_executed_nonzero"]:
        print("FAILED:TST-0111-probe1 false was not executed as broken")
        return 1
    if not controls["sudo_not_executed"]:
        print("FAILED:TST-0111-probe1 sudo ran or lacked marker")
        return 1
    if controls["bad_coverage"] is not False:
        print("FAILED:TST-0111-probe1 unmarked curl was treated as covered")
        return 1
    unmarked = controls["unmarked_exclusion"]["table"]
    if not unmarked or unmarked[0].get("executed") is not False:
        print("FAILED:TST-0111-probe1 unmarked curl was spawned")
        return 1
    if unmarked[0].get("classification") != "broken-unmarked-exclusion":
        print("FAILED:TST-0111-probe1 unmarked curl classification")
        return 1
    if int(controls["planted"].get("unlabeled_table_count", -1)) != 0:
        print("FAILED:TST-0111-probe1 unlabeled table extracted as commands")
        return 1

    print("SUCCESS:TST-0111-probe1 every command executed or marked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
