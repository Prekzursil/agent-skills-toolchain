#!/usr/bin/env python3
"""Probe 2: silent-degradation detector + full-grant control.

Honest subject must fail loudly when Write is denied. The silent mutant must
report success without a transcript and without marking degraded; this probe
fails if that mutant is not detected. The full-grant control must still pass.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog_perms as C  # noqa: E402
import subject as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0040-least-privilege-confirm.json"
DENIED = "Write"


def _payload(doc: dict) -> dict:
    """Domain fields live under report (receipt_core forbids extra top-level keys)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    merged = dict(ext)
    merged.update(report)
    for key in (
        "state",
        "sentinel",
        "silent_degradation",
        "reduced_run",
        "full_run",
        "outcomes_relation",
    ):
        if key in doc and key not in {"report", "extensions"}:
            if key in {"state", "sentinel"} or key not in merged:
                merged[key] = doc[key]
    return merged


def _detector_fired(mutant: dict) -> bool:
    return bool(
        mutant.get("ok")
        and not mutant.get("transcript_written")
        and not mutant.get("artifact_marked_degraded")
        and mutant.get("classification") == "silent-degradation"
    )


def main() -> int:
    impl = C.implementing()
    declared = impl["declared_permissions"]
    if DENIED not in declared:
        print(f"FAILED:CNF-0040-probe2 {DENIED} is not in declared set {declared}")
        return 1
    stripped = [p for p in declared if p != DENIED]
    full = C.full_grant(declared)
    with tempfile.TemporaryDirectory(prefix="cnf0040-p2-") as tmp:
        base = Path(tmp)
        honest = S.verify_honest(stripped, declared, base / "honest-nowrite")
        mutant = S.verify_silent(stripped, declared, base / "mutant-nowrite")
        control = S.verify_honest(full, declared, base / "control-full")
    fired = _detector_fired(mutant)
    print(
        json.dumps(
            {
                "probe": "probe2-silent-degradation",
                "unit_id": "CNF-0040",
                "denied_permission": DENIED,
                "honest_ok": honest["ok"],
                "honest_class": honest["classification"],
                "honest_error": honest["error_text"],
                "mutant_ok": mutant["ok"],
                "mutant_transcript_written": mutant["transcript_written"],
                "mutant_marked_degraded": mutant["artifact_marked_degraded"],
                "detector_fired": fired,
                "control_ok": control["ok"],
                "control_transcript_written": control["transcript_written"],
            },
            sort_keys=True,
        )
    )
    if honest["ok"] or honest["classification"] != "loud-deny":
        print("FAILED:CNF-0040-probe2 honest subject did not fail loudly without Write")
        return 1
    if DENIED not in honest["error_text"]:
        print("FAILED:CNF-0040-probe2 deny error does not name Write")
        return 1
    if not fired:
        print("FAILED:CNF-0040-probe2 silent-degradation detector did not fire")
        return 1
    if not control["ok"] or not control["transcript_written"]:
        print("FAILED:CNF-0040-probe2 full-grant control did not pass")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0040-probe2 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = _payload(doc)
    if payload.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0040-probe2 artifact state={payload.get('state')}")
        return 1
    sd = payload.get("silent_degradation") or {}
    if sd.get("probed") is not True or sd.get("detector_fired") is not True:
        print("FAILED:CNF-0040-probe2 artifact did not record the detector firing")
        return 1
    if not (payload.get("reduced_run") or {}).get("ok"):
        print("FAILED:CNF-0040-probe2 artifact reduced_run is not ok")
        return 1
    if not (payload.get("full_run") or {}).get("ok"):
        print("FAILED:CNF-0040-probe2 artifact full_run is not ok")
        return 1
    if payload.get("outcomes_relation") not in {
        "explained",
        "differ",
        "differ-and-explained",
    }:
        print("FAILED:CNF-0040-probe2 artifact outcomes_relation missing")
        return 1
    sentinel = str(payload.get("sentinel") or doc.get("sentinel") or "")
    if "SUCCESS:CNF-0040" not in sentinel:
        print("FAILED:CNF-0040-probe2 sentinel missing in artifact")
        return 1
    print(
        f"honest_loud={not honest['ok']} detector_fired={fired} "
        f"control_ok={control['ok']}"
    )
    print("SUCCESS:CNF-0040-probe2 silent-degradation detector and full-grant control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
