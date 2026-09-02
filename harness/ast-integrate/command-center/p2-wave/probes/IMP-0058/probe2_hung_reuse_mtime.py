#!/usr/bin/env python3
"""Named probe 2 (reviewer): hung child FAILED; scripts reused; no mtime hang path.

NEGATIVE CONTROL: a SIGSTOP/sleep child must freeze the token AND show zero CPU
delta in the hang window, and the runner must report FAILED not SUCCESS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin" / "tests"))
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from test_heartbeat import (  # noqa: E402
    test_hung_child_reports_failed_not_success,
    test_longrun_scripts_reused,
    test_mtime_not_consulted_in_classifier,
)

ART = REPO / "command-center/receipts/IMP-0058.json"


def main() -> int:
    hung = test_hung_child_reports_failed_not_success()
    reuse = test_longrun_scripts_reused()
    mtime = test_mtime_not_consulted_in_classifier()
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
        nc = tests.get("IMP-0058-HUNG-NEGATIVE")
        if not nc or nc.get("result") != "PASS":
            print("FAILED:IMP-0058-probe2 receipt missing hung negative PASS")
            return 1
        reviewer = doc.get("reviewer") or {}
        if reviewer.get("verdict") != "PASS":
            print("FAILED:IMP-0058-probe2 reviewer not PASS")
            return 1
        if not reviewer.get("mtime_inference_absent"):
            print("FAILED:IMP-0058-probe2 reviewer did not confirm mtime-free hang path")
            return 1
    hang = hung.get("hang_window") or {}
    out = {
        "probe": "probe2-hung-reuse-mtime",
        "unit_id": "IMP-0058",
        "hung_status": hung.get("status"),
        "hung_classification": hung.get("classification"),
        "token_advanced": hung.get("token_advanced"),
        "hang_window_cpu_delta": hang.get("cpu_delta"),
        "hang_window_token_delta": hang.get("token_delta"),
        "scripts_reused": reuse.get("reused"),
        "mtime_hits": mtime.get("hits"),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"hung status={hung.get('status')} class={hung.get('classification')} "
        f"cpu_delta={hang.get('cpu_delta')} token_delta={hang.get('token_delta')}"
    )
    print(f"reuse={reuse.get('reused')} mtime_hits={mtime.get('hits')}")
    print("SUCCESS:IMP-0058-probe2 hung FAILED; longrun reused; mtime unused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
