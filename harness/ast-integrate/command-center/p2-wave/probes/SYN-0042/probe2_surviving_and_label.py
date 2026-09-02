#!/usr/bin/env python3
"""Named probe 2: nonempty caveats on survivors; VERIFIED+fatal is a labelling error."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import claims as C  # noqa: E402
import detector as D  # noqa: E402

FIXTURES = HERE / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def main() -> int:
    fatal = load("verified-fatal.json")
    cond = load("verified-conditional.json")
    fatal_hit = D.label_contradiction(fatal["label"], fatal["caveat"])
    cond_hit = D.label_contradiction(cond["label"], cond["caveat"])
    if not fatal_hit:
        print("FAILED:SYN-0042-probe2 VERIFIED+fatal caveat did not fire labelling error")
        return 1
    if cond_hit:
        print("FAILED:SYN-0042-probe2 VERIFIED+conditional caveat fired labelling error")
        return 1

    packed = C.load_audit_claims()
    items = packed["items"]
    if not items:
        print("FAILED:SYN-0042-probe2 no surviving claims to audit")
        return 1
    audited = [D.enforce(item) for item in items]
    missing = [a["claim_id"] for a in audited if not (a.get("caveat") or "").strip()]
    if missing:
        print(f"FAILED:SYN-0042-probe2 empty caveat on {missing}")
        return 1
    remaining = [a["claim_id"] for a in audited if a.get("remaining_vacuous")]
    if remaining:
        print(f"FAILED:SYN-0042-probe2 vacuous caveat remaining on {remaining}")
        return 1
    contradictions = [a["claim_id"] for a in audited if a.get("label_contradiction")]
    if contradictions:
        print(
            f"FAILED:SYN-0042-probe2 VERIFIED+fatal labelling error on {contradictions}"
        )
        return 1
    rejected = packed.get("rejected_skipped") or []
    if "SC-DEAD" in {i["id"] for i in C.load_fixture_claims()} and "SC-DEAD" not in rejected:
        # Fixture corpus must skip REJECTED. Live SYN-0041 may not include SC-DEAD.
        if packed["source"].startswith("fixture") and "SC-DEAD" not in rejected:
            print("FAILED:SYN-0042-probe2 REJECTED fixture was treated as surviving")
            return 1

    print(
        json.dumps(
            {
                "verified_fatal_flagged": True,
                "verified_conditional_silent": True,
                "surviving_claims": len(audited),
                "empty_caveats": 0,
                "vacuous_remaining": 0,
                "label_contradictions": 0,
                "rejected_skipped": rejected,
                "source": packed["source"],
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:SYN-0042-probe2 every surviving claim has a nonempty non-vacuous "
        "caveat; VERIFIED+fatal is a labelling error"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
