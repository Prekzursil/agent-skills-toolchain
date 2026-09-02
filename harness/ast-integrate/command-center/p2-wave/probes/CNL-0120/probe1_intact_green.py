#!/usr/bin/env python3
"""Probe 1: intact scripted council with exactly one dissent is GREEN.

Signal A: preserve.check set-diff + token/counterexample.
Signal B: token string search on serialized synthesis (different mechanism).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import preserve as P  # noqa: E402
import recount as R  # noqa: E402

OUT = HERE / "probe1-intact.raw.json"
ART = (
    HERE.parents[3]
    / "command-center/design/council"
    / "CNL-0120-dissent-preservation-simulation-with-a-planted-dropped-dis.md"
)
SENTINEL = "SUCCESS:CNL-0120"


def main() -> int:
    script = H.load_fixture()
    try:
        d = H.assert_exactly_one_dissent(script)
    except ValueError as exc:
        print(f"FAILED:CNL-0120-probe1 fixture {exc}")
        return 1
    run = H.run_intact(script)
    chk = P.check(run["transcript"], run["synthesis"])
    lost = R.lost_ids(run)
    tok = R.token_present(run, d["token"])
    cex = R.counterexample_present(run, d["counterexample"])
    vacuous = P.vacuous_nonempty(run["synthesis"])
    doc = {
        "probe": "probe1",
        "unit_id": "CNL-0120",
        "dissent_count": 1,
        "claim_id": d["claim_id"],
        "token": d["token"],
        "preserve_verdict": chk["verdict"],
        "preserve_fired": chk["fired"],
        "recount_lost": lost,
        "token_in_synthesis": tok,
        "counterexample_in_synthesis": cex,
        "vacuous_nonempty_green": vacuous,
        "signals": [
            "preserve.check claim-id set-diff",
            "recount.token_present string search on synthesis JSON",
        ],
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if chk["verdict"] != "GREEN" or chk["fired"] is not False:
        print("FAILED:CNL-0120-probe1 intact not GREEN", json.dumps(chk, sort_keys=True))
        return 1
    if lost:
        print("FAILED:CNL-0120-probe1 recount lost=" + ",".join(lost))
        return 1
    if not tok or not cex:
        print("FAILED:CNL-0120-probe1 token-or-counterexample-missing")
        return 1
    if not vacuous:
        print("FAILED:CNL-0120-probe1 intact synthesis empty")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            art = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"FAILED:CNL-0120-probe1 artifact-unparseable {exc}")
            return 1
        st = str(art.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:CNL-0120-probe1 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:CNL-0120-probe1 sentinel-absent")
            return 1
        intact = (art.get("both_states") or {}).get("intact") or {}
        if str(intact.get("verdict") or "").upper() != "GREEN":
            print("FAILED:CNL-0120-probe1 artifact intact verdict drift")
            return 1
        doc["artifact_checked"] = True
    else:
        doc["artifact_checked"] = False
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "intact_verdict=GREEN dissent_count=1 lost=0 token_present=True "
        f"counterexample_present=True vacuous_nonempty={vacuous} "
        f"artifact_checked={doc['artifact_checked']}"
    )
    print("SUCCESS:CNL-0120-probe1 intact dissent preserved (GREEN)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
