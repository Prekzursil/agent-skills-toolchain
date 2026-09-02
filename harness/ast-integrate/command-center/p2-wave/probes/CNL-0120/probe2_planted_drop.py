#!/usr/bin/env python3
"""Probe 2: planted drop turns the check RED; independent recount agrees.

Also records the negative control verbatim and shows a vacuous nonempty
check stays green on the dropped synthesis (so it measures nothing).
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

OUT = HERE / "probe2-planted-drop.raw.json"
ART = (
    HERE.parents[3]
    / "command-center/design/council"
    / "CNL-0120-dissent-preservation-simulation-with-a-planted-dropped-dis.md"
)
SENTINEL = "SUCCESS:CNL-0120"


def main() -> int:
    script = H.load_fixture()
    d = H.assert_exactly_one_dissent(script)
    intact = H.run_intact(script)
    planted = H.plant_drop(intact)
    chk_good = P.check(intact["transcript"], intact["synthesis"])
    chk_bad = P.check(planted["transcript"], planted["synthesis"])
    lost = R.lost_ids(planted)
    tok = R.token_present(planted, d["token"])
    cex = R.counterexample_present(planted, d["counterexample"])
    vacuous_bad = P.vacuous_nonempty(planted["synthesis"])
    vacuous_good = P.vacuous_nonempty(intact["synthesis"])
    blob = json.dumps(planted["synthesis"], ensure_ascii=True)
    generic = H.GENERIC_DROP_PHRASE.lower() in blob.lower()
    verbatim = json.dumps(
        {
            "verdict": chk_bad["verdict"],
            "fired": chk_bad["fired"],
            "lost_claim_ids": chk_bad["lost_claim_ids"],
            "token_present": chk_bad["token_present"],
            "counterexample_present": chk_bad["counterexample_present"],
            "generic_phrase_only": chk_bad["generic_phrase_only"],
            "reason": chk_bad["reason"],
        },
        sort_keys=True,
    )
    doc = {
        "probe": "probe2",
        "unit_id": "CNL-0120",
        "intact_verdict": chk_good["verdict"],
        "planted_verdict": chk_bad["verdict"],
        "planted_fired": chk_bad["fired"],
        "recount_lost": lost,
        "token_in_dropped_synthesis": tok,
        "counterexample_in_dropped_synthesis": cex,
        "vacuous_green_on_intact": vacuous_good,
        "vacuous_green_on_planted_drop": vacuous_bad,
        "generic_phrase_present": generic,
        "negative_control_verbatim": verbatim,
        "signals": [
            "preserve.check fired on planted drop",
            "recount.lost_ids independent set-diff (no preserve.check)",
        ],
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if chk_good["verdict"] != "GREEN":
        print("FAILED:CNL-0120-probe2 intact not GREEN")
        return 1
    if chk_bad["verdict"] != "RED" or not chk_bad["fired"]:
        print("FAILED:CNL-0120-probe2 planted drop did not turn RED", verbatim)
        return 1
    if lost != [d["claim_id"]]:
        print("FAILED:CNL-0120-probe2 recount lost mismatch", lost)
        return 1
    if tok or cex:
        print("FAILED:CNL-0120-probe2 residue of token or counterexample")
        return 1
    if not generic:
        print("FAILED:CNL-0120-probe2 planted generic phrase missing")
        return 1
    if not (vacuous_good and vacuous_bad):
        print("FAILED:CNL-0120-probe2 vacuous check not green in both states")
        return 1
    if not chk_bad["generic_phrase_only"]:
        print("FAILED:CNL-0120-probe2 generic-only not detected")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            art = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"FAILED:CNL-0120-probe2 artifact-unparseable {exc}")
            return 1
        if SENTINEL not in text:
            print("FAILED:CNL-0120-probe2 sentinel-absent")
            return 1
        drop = (art.get("both_states") or {}).get("planted_drop") or {}
        if str(drop.get("verdict") or "").upper() != "RED":
            print("FAILED:CNL-0120-probe2 artifact planted_drop verdict drift")
            return 1
        nc = art.get("negative_control") or {}
        does = str(nc.get("check_does") or nc.get("check_does") or "")
        if "RED" not in does and "FIRE" not in does.upper():
            print("FAILED:CNL-0120-probe2 artifact negative_control missing FIRE/RED")
            return 1
        doc["artifact_checked"] = True
    else:
        doc["artifact_checked"] = False
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "intact=GREEN planted_drop=RED recount_lost="
        + ",".join(lost)
        + f" vacuous_both_green={vacuous_good and vacuous_bad}"
        + f" generic_only={chk_bad['generic_phrase_only']}"
        + f" artifact_checked={doc['artifact_checked']}"
    )
    print("negative_control_reject_state=synthesis with dissent stripped, generic phrase left")
    print("negative_control_verbatim=" + verbatim)
    print("SUCCESS:CNL-0120-probe2 planted drop turns check RED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
