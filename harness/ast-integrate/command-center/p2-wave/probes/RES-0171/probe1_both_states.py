#!/usr/bin/env python3
"""Probe 1: both-states resume — reuse unchanged, refetch mutated fixture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
import schema_ctl  # noqa: E402

ART = (
    S.REPO
    / "command-center/research/deep-research-design"
    / "RES-0171-research-cache-key-and-resume.json"
)


def main() -> int:
    live = S.run_both_states()
    printable = {k: v for k, v in live.items() if k != "body"}
    print(json.dumps(printable, sort_keys=True, default=str))
    if not live.get("pass"):
        print("FAILED:RES-0171-probe1 both-states unpaid")
        return 1
    if live.get("stable_resume_action") != "reuse":
        print("FAILED:RES-0171-probe1 unchanged origin was not reused")
        return 1
    if live.get("mutated_resume_action") != "refetch":
        print("FAILED:RES-0171-probe1 mutated origin was not refetched")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:RES-0171" not in text:
            print("FAILED:RES-0171-probe1 sentinel-absent")
            return 1
        doc = json.loads(text)
        payload = schema_ctl.domain_payload(doc)
        recorded = (payload.get("both_states") or {}).get("stable_resume_action")
        if recorded != "reuse":
            print(f"FAILED:RES-0171-probe1 artifact drift recorded={recorded}")
            return 1
    print(
        "reuse={u} refetch={r} keys_distinct={k} fetches={f}".format(
            u=live["stable_resume_action"],
            r=live["mutated_resume_action"],
            k=live["keys_distinct"],
            f=live["fetches"],
        )
    )
    print("SUCCESS:RES-0171-probe1 both-states reuse-and-refetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
