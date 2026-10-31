#!/usr/bin/env python3
"""RES-0175 probe2_lineage_overclaim.

tests row: named-probe-2. Verifies every lineage entry carries resolved URL +
fetch timestamp + sha256, and that the honest NEUTRALISED-vs-MERELY-DETECTED
distinction is recorded (capability_withdrawal caught 0 NEUTRALISED and says
so, with the residual honestly carried rather than dressed up). Defaults to
FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/deep-research-design/RES-0175-fetched-content-injection-filter.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:240]})
        return bool(ok)

    sl = doc.get("source_lineage") or []
    ck("lineage-present", len(sl) >= 3, f"n={len(sl)}")
    ok_fields = all(
        s.get("resolved_url") and s.get("fetch_timestamp") and s.get("sha256")
        for s in sl
    )
    ck("lineage-url-timestamp-sha", ok_fields,
       str([bool(s.get("sha256")) for s in sl]))
    ck("sha-shape", all(len(str(s.get("sha256"))) == 64 for s in sl), "sha256[64]")

    measured = (doc.get("measured") or {}).get("by_filter") or {}
    cw = measured.get("capability_withdrawal") or {}
    ck("neutralised-not-dressed-as-detection",
       cw.get("neutralised") == 0 and float(cw.get("catch_rate_neutralised", -1)) == 0.0
       and int(cw.get("merely_detected", 0)) > 0,
       json.dumps({k: cw.get(k) for k in ("neutralised", "catch_rate_neutralised", "merely_detected")}))
    st = measured.get("instruction_stripping") or {}
    ck("false-positives-counted-separately",
       int(st.get("false_positives", 0)) == 10 and int(st.get("mention_n", 0)) == 10,
       json.dumps({k: st.get(k) for k in ("false_positives", "mention_n", "false_positive_rate")}))
    ck("honest-miss-rate-recorded",
       any(float(m.get("miss_rate", -1)) > 0 for m in measured.values()),
       str({f: m.get("miss_rate") for f, m in measured.items()}))

    nvd = doc.get("neutralised_vs_merely_detected") or {}
    ck("distinction-block-present", bool(nvd), json.dumps(nvd, default=str)[:160])

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and "SUCCESS:RES-0175" in txt,
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe2-lineage-overclaim", "unit_id": "RES-0175", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0175-probe2 lineage complete, no neutralisation overclaim" if not red
          else f"FAILED:RES-0175-probe2 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
