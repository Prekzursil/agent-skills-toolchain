#!/usr/bin/env python3
"""Named probe 2: behavioural disconnect + P1 certification gate.

Mechanically different from probe 1: this probe exercises the distinctive
RETRY-TOKEN through source vs fused pipelines (a token is either produced or
not; it does not score incidence-cell set difference). It also calls
attempt_certify and requires REFUSED with a null certification record on a
failing fusion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from detector import attempt_certify, detect_fusion, exercise  # noqa: E402
from fixtures import (  # noqa: E402
    FUSION_DISC,
    FUSION_KEEP,
    FUSION_LOSS,
    MECH_RETRY,
    SEVERITY_P1,
    SRC_ALPHA,
    SRC_BETA,
    SRC_GAMMA,
    UNIT,
)

ART = REPO / "command-center/wfa/WFA-0108-fusion-capability-loss-detector.json"
SENTINEL = f"SUCCESS:{UNIT}"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if SENTINEL not in json.dumps(doc):
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    src_run = exercise(SRC_BETA, MECH_RETRY)
    keep_run = exercise(FUSION_KEEP, MECH_RETRY)
    disc_run = exercise(FUSION_DISC, MECH_RETRY)
    loss_run = exercise(FUSION_LOSS, MECH_RETRY)

    if not src_run["pass"] or not src_run["token_present"]:
        return fail("source retry behaviour dead", src_run)
    if not keep_run["pass"] or not keep_run["token_present"]:
        return fail("lossless fusion dropped retry behaviour", keep_run)
    if disc_run["token_present"] or disc_run["reached"]:
        return fail("disconnected fusion still produced retry token", disc_run)
    if loss_run["token_present"] or loss_run["reached"]:
        return fail("lossy fusion still produced retry token", loss_run)

    disc_v = detect_fusion(FUSION_DISC, [SRC_ALPHA, SRC_BETA])
    loss_v = detect_fusion(FUSION_LOSS, [SRC_ALPHA, SRC_BETA])
    keep_v = detect_fusion(FUSION_KEEP, [SRC_ALPHA, SRC_BETA, SRC_GAMMA])

    if MECH_RETRY not in disc_v["signal_b"]["missing"]:
        return fail("behaviour signal missed disconnect", disc_v["signal_b"])
    if disc_v["signal_a"]["missing"]:
        return fail("matrix falsely flagged disconnect", disc_v["signal_a"])

    cert_keep = attempt_certify(keep_v)
    cert_disc = attempt_certify(disc_v)
    cert_loss = attempt_certify(loss_v)
    if cert_keep["status"] != "ADMITTED" or cert_keep.get("certification_record") is None:
        return fail("lossless not admitted", cert_keep)
    if cert_disc["status"] != "REFUSED" or cert_disc.get("certification_record") is not None:
        return fail("disconnected not refused", cert_disc)
    if cert_loss["status"] != "REFUSED" or cert_loss.get("certification_record") is not None:
        return fail("lossy not refused", cert_loss)
    if cert_disc.get("severity") != SEVERITY_P1 or cert_loss.get("severity") != SEVERITY_P1:
        return fail("severity not P1", {"disc": cert_disc, "loss": cert_loss})

    gate = doc.get("certification_gate") or {}
    refused = gate.get("refused") or []
    if not refused:
        return fail("artifact refused list empty")
    for row in refused:
        if row.get("certification_record") is not None:
            return fail("artifact refused row still has a record", row)
        if row.get("status") != "REFUSED":
            return fail("artifact refused status", row)
    admitted = gate.get("admitted") or []
    if not any(
        r.get("fusion_id") == "fusion-keep" and r.get("status") == "ADMITTED"
        for r in admitted
    ):
        return fail("artifact missing lossless admission", admitted)
    controls = doc.get("controls") or {}
    if not (controls.get("p1_certification_refusal") or {}).get("pass"):
        return fail("artifact p1 gate control not pass")
    if not (controls.get("disconnected_capability_behavioural") or {}).get("pass"):
        return fail("artifact disconnect control not pass")

    payload = {
        "pass": True,
        "probe": "probe2-disconnect-and-p1-gate",
        "unit_id": UNIT,
        "source_retry_token": src_run["token"],
        "disconnected_token_present": disc_run["token_present"],
        "lossy_token_present": loss_run["token_present"],
        "keep_token_present": keep_run["token_present"],
        "disconnected_certify": cert_disc["status"],
        "lossy_certify": cert_loss["status"],
        "keep_certify": cert_keep["status"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "source_retry=True disc_token=False loss_token=False "
        "disc_certify=REFUSED loss_certify=REFUSED keep_certify=ADMITTED"
    )
    print(f"SUCCESS:{UNIT}-probe2 behavioural-disconnect and P1 certification gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
