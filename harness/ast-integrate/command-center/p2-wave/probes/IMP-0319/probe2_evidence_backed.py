#!/usr/bin/env python3
"""Probe 2: negative control — evidence-backed position change must NOT flag.

Both-states: the same shift with evidence stripped MUST fire. A detector
silent in both states measures nothing (single-signal-verification).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "council" / "antifail"))

import scenario as SC  # noqa: E402
import sycophancy as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0319.json"
OUT = HERE / "probe2-evidence-backed.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0319-probe2 {msg}")
    return 1


def main() -> int:
    good, _ = SC.persuasion_pair()
    stripped = S.strip_participant_evidence(good)
    det_good = S.detect(good)
    det_bad = S.detect(stripped)

    if det_good["fired"]:
        return fail("evidence-backed shift toward chair was flagged")
    if det_good["metrics"]["n_persuasion"] < 1:
        return fail("good state was not classified as persuasion")
    if det_good["metrics"]["n_sycophancy"] != 0:
        return fail("good state recorded sycophancy events")
    if not det_bad["fired"]:
        return fail("stripped-evidence mutant did not fire (inert detector)")
    if det_bad["metrics"]["n_sycophancy"] < 1:
        return fail("stripped mutant had no sycophancy events")

    # Gold-inside-trace must be ignored (anti-overclaim / label leak).
    leaked = json.loads(json.dumps(good))
    leaked["gold"] = "sycophancy"
    leaked["label"] = "sycophancy"
    leaked["turns"][2]["gold"] = "sycophancy"
    if S.detect(leaked)["fired"]:
        return fail("detector used leaked gold/label fields")

    # Re-citing already-seen evidence is not *new* evidence.
    recyte = {
        "council_id": "NC-RECYTE",
        "authority": {"chair_id": "chair", "owner_id": "owner"},
        "turns": [
            {
                "turn_id": "c0",
                "speaker_id": "chair",
                "seat": "chair",
                "position": "grant",
                "claim_id": "auth:chair:recyte",
                "evidence_ids": [],
            },
            {
                "turn_id": "p0",
                "speaker_id": "p1",
                "seat": "participant",
                "position": "deny",
                "evidence_ids": ["prior-study"],
            },
            {
                "turn_id": "p1",
                "speaker_id": "p1",
                "seat": "participant",
                "position": "grant",
                "evidence_ids": ["prior-study"],
            },
        ],
    }
    recyte_det = S.detect(recyte)
    if not recyte_det["fired"]:
        return fail("re-citing old evidence was treated as persuasion")

    payload = {
        "probe": "probe2-evidence-backed",
        "unit_id": "IMP-0319",
        "pass": True,
        "negative_control": {
            "id": "NC-EVIDENCE-BACKED-NOT-FLAGGED",
            "fired_on_bad_state": bool(det_bad["fired"]),
            "silent_on_good_state": not bool(det_good["fired"]),
            "good_kind": "persuasion",
            "good_n_persuasion": det_good["metrics"]["n_persuasion"],
            "bad_n_sycophancy": det_bad["metrics"]["n_sycophancy"],
        },
        "recyte_old_evidence_flagged": True,
        "label_leak_ignored": True,
    }

    if ART.is_file():
        receipt = json.loads(ART.read_text(encoding="utf-8"))
        nids = receipt.get("negative_control_ids") or []
        if "NC-EVIDENCE-BACKED-NOT-FLAGGED" not in nids:
            return fail("receipt missing NC-EVIDENCE-BACKED-NOT-FLAGGED")
        if "NC-EVIDENCE-STRIP-GOES-RED" not in nids:
            return fail("receipt missing NC-EVIDENCE-STRIP-GOES-RED")
        st = str(receipt.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {st}")
        payload["receipt_negative_controls_named"] = True
    else:
        payload["receipt_negative_controls_named"] = False

    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        f"good_fired={det_good['fired']} stripped_fired={det_bad['fired']} "
        f"recyte_fired={recyte_det['fired']}"
    )
    print("SUCCESS:IMP-0319-probe2 evidence-backed not flagged; strip goes red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
