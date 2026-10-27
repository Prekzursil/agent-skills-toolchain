#!/usr/bin/env python3
"""RES-0179 probe1_detector_control.

tests row: T1-detector-control - fetch a known-reachable control URL through
the same path and require success, so a blocked verdict cannot be a broken
fetcher. LIVE leg re-runs the control fetch now (the always-on local health
endpoint); offline leg verifies the recorded detector-control block and the
barrier survey rows all carry their recorded fetch evidence. Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/sources-frontier/RES-0179-jurisdiction-source-accessibility-scoping.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:240]})
        return bool(ok)

    # LIVE control: same fetch path as the measurement, known-reachable
    try:
        with urllib.request.urlopen("http://127.0.0.1:18812/api/health", timeout=6) as r:
            live_ok = r.status == 200
    except Exception as exc:
        live_ok = False
        print(f"LIVE-CONTROL-FAILED: {type(exc).__name__}")
    ck("live-control-reachable-through-same-path", live_ok, "local always-on health endpoint, 200")

    dc = doc.get("detector_control") or {}
    be = dc.get("blocked_example") or {}
    ck("recorded-blocked-example-carries-body-evidence",
       bool(be.get("body_head_excerpt")) and bool(be.get("http_status") is not None
                                                  or be.get("waf_action")),
       f"status={be.get('http_status')} waf={be.get('waf_action')} "
       f"head={str(be.get('body_head_excerpt'))[:80]}")
    ctl = dc.get("control") or {}
    ck("recorded-control-ok-and-evidenced",
       dc.get("control_ok") is True and ctl.get("ok_2xx") is True and ctl.get("http_status") == 200,
       f"control_ok={dc.get('control_ok')} http={ctl.get('http_status')}")
    ng = dc.get("negative_control") or {}
    ck("recorded-negative-control-fails-as-required",
       dc.get("negative_not_ok") is True and ng.get("ok_2xx") is False,
       f"negative_not_ok={dc.get('negative_not_ok')} ok_2xx={ng.get('ok_2xx')}")

    bs = doc.get("barrier_survey") or []
    ck("nine-barrier-rows", len(bs) == 9, f"n={len(bs)}")
    ck("every-row-carries-fetch-evidence",
       all((b.get("fetch") or {}).get("body_head_excerpt") or (b.get("fetch") or {}).get("status")
           for b in bs),
       str([b.get("expect_kind") for b in bs]))
    ck("expect-kinds-classified",
       all(b.get("expect_kind") for b in bs),
       str(sorted({b.get("expect_kind") for b in bs})))

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and doc.get("completion_sentinel") == "SUCCESS:RES-0179",
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-detector-control", "unit_id": "RES-0179", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0179-probe1 detector control re-run live, survey rows evidenced" if not red
          else f"FAILED:RES-0179-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
