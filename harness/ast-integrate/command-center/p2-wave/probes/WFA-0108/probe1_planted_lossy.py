#!/usr/bin/env python3
"""Named probe 1: both-states + planted lossy fusion caught by BOTH signals.

Signal: set-difference of incidence cells (A) AND token presence on the fused
pipeline (B). A planted drop of mech.retry-recovery must appear in both missing
sets. Divergence on a disconnected fusion is reported as its own finding.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from detector import scan_corpus  # noqa: E402
from fixtures import FUSIONS, MECH_LICENSE, MECH_RETRY, UNIT  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0108-fusion-capability-loss-detector.json"
SENTINEL = f"SUCCESS:{UNIT}"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def by_id(verdicts):
    return {v["fusion_id"]: v for v in verdicts}


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

    live = scan_corpus(FUSIONS)
    live_map = by_id(live["verdicts"])
    art_map = by_id(doc.get("fusions") or [])
    keep = live_map["fusion-keep"]
    loss = live_map["fusion-lossy-planted"]
    disc = live_map["fusion-disconnected"]
    phantom = live_map["fusion-phantom-declaration"]

    if keep["detector_fired"]:
        return fail("lossless fusion fired detector", keep)
    if not keep["may_proceed_to_certification"]:
        return fail("lossless fusion blocked certification")
    if keep["signal_a"]["missing"] or keep["signal_b"]["missing"]:
        return fail("lossless missing non-empty", keep)

    if not loss["detector_fired"]:
        return fail("planted lossy silent")
    if MECH_RETRY not in loss["signal_a"]["missing"]:
        return fail("signal A missed planted loss", loss["signal_a"])
    if MECH_RETRY not in loss["signal_b"]["missing"]:
        return fail("signal B missed planted loss", loss["signal_b"])
    if loss["divergence"]["present"]:
        return fail("planted lossy should agree on missing set", loss["divergence"])
    if loss["may_proceed_to_certification"]:
        return fail("planted lossy allowed to certify")

    if disc["signal_a"]["missing"]:
        return fail("disconnected should be silent on matrix", disc["signal_a"])
    if MECH_RETRY not in disc["signal_b"]["missing"]:
        return fail("disconnected not caught by behaviour", disc["signal_b"])
    if not disc["divergence"]["present"]:
        return fail("disconnected divergence not reported", disc["divergence"])
    if MECH_RETRY not in disc["divergence"]["only_in_behaviour"]:
        return fail("divergence did not name retry-recovery", disc["divergence"])

    if not phantom["divergence"]["present"]:
        return fail("phantom divergence not reported", phantom["divergence"])
    if phantom["divergence"]["only_in_matrix"] != [MECH_LICENSE]:
        return fail("phantom only_in_matrix", phantom["divergence"])

    art_loss = art_map.get("fusion-lossy-planted") or {}
    if MECH_RETRY not in ((art_loss.get("signal_a") or {}).get("missing") or []):
        return fail("artifact signal A drift", art_loss.get("signal_a"))
    if MECH_RETRY not in ((art_loss.get("signal_b") or {}).get("missing") or []):
        return fail("artifact signal B drift", art_loss.get("signal_b"))
    controls = doc.get("controls") or {}
    if not (controls.get("both_states") or {}).get("pass"):
        return fail("artifact both_states not pass")
    if not (controls.get("planted_lossy_caught_by_both_signals") or {}).get("pass"):
        return fail("artifact planted control not pass")

    payload = {
        "pass": True,
        "probe": "probe1-planted-lossy-both-signals",
        "unit_id": UNIT,
        "lossless_silent": True,
        "lossy_signal_a_missing": loss["signal_a"]["missing"],
        "lossy_signal_b_missing": loss["signal_b"]["missing"],
        "caught_by_both": True,
        "disconnected_divergence": disc["divergence"]["present"],
        "phantom_divergence": phantom["divergence"]["present"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "lossless_silent=True planted_both_signals=True "
        f"missing={MECH_RETRY} disconnected_divergence=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 planted-lossy both-signals and divergence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
