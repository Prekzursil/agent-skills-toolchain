#!/usr/bin/env python3
"""Wave-4 shard-2 receipt normalization (receipt_core form).

For 10 units whose SUBAGENT-RETURN.json carries state=SUCCESS without an
independent reviewer closure (reviewer.verdict=PASS + independent=true),
restore the program-contract receipt form: state=BLOCKED,
failure.classification=["reviewer-absent"], reviewer field preserved verbatim
(NOT-REVIEWED / absent both stay - they are honest disclosures), any
extensions.prev_closure entries preserved, dated note appended.

ADV-0127 and ARC-0054 already conform and are left untouched. ARC-0013's own
notes already claim "Receipt held BLOCKED (reviewer-absent)" while its state
field says SUCCESS - this restores the state the builder recorded in prose.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
UNITS = [
    "ADV-0128",
    "ARC-0001",
    "ARC-0012",
    "ARC-0013",
    "ARC-0015",
    "ARC-0019",
    "ARC-0020",
    "ARC-0021",
    "ARC-0047",
    "ARC-0048",
]
REASON = (
    "Builder lane may not self-certify: artifact live-verified, named probes "
    "re-run exit 0, per-unit manifest sha rows match; receipt stays BLOCKED "
    "until the independent reviewer closes (reviewer.verdict=PASS with "
    "independent=true)."
)


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    changed = []
    for uid in UNITS:
        rp = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
        if not rp.is_file():
            print(f"FAILED:normal {uid} receipt absent")
            return 1
        ret = json.loads(rp.read_text(encoding="utf-8"))
        rv = ret.get("reviewer")
        if isinstance(rv, dict) and rv.get("verdict") == "PASS" and rv.get("independent") is True:
            print(f"SKIP {uid}: independent closure present, kept")
            continue
        before = ret.get("state")
        ret["state"] = "BLOCKED"
        fail = ret.get("failure") if isinstance(ret.get("failure"), dict) else {}
        cls = fail.get("classification") or ["reviewer-absent"]
        if "reviewer-absent" not in cls:
            cls.append("reviewer-absent")
        fail["classification"] = cls
        if not fail.get("reason"):
            fail["reason"] = REASON
        ret["failure"] = fail
        note = (
            f"Wave-4 shard-2 builder {now}: receipt form normalized per "
            "receipt_core - state "
            f"{before}->BLOCKED, failure.classification=['reviewer-absent']. "
            "Prior builder-authored probe closures are recorded in "
            "extensions.prev_closure but do not satisfy the independence "
            "requirement (demotion precedent ADV-0128 2026-10-25: only the "
            "independent reviewer closes). Artifact and probes unchanged and "
            "live-verified this session."
        )
        prev = str(ret.get("notes") or "").strip()
        ret["notes"] = (prev + "\n" if prev else "") + note
        rp.write_text(json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        changed.append(f"{uid} {before}->BLOCKED")
    print("; ".join(changed) if changed else "no changes")
    print(f"SUCCESS:normal {len(changed)}/{len(UNITS)} receipts normalized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
