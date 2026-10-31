#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "RES-0188"
OUT = (REPO / "command-center/research/evidence-quality/RES-0188-stale-premise-detection-in-briefing-packs.json").resolve()


def fail(msg):
    print(f"FAILED:{UID}-probe {msg}")
    raise SystemExit(1)


def ok(*parts):
    print("PROBE-OK", UID, *parts)


def load():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"artifact unreadable: {type(exc).__name__}: {exc}")


def need(cond, msg):
    if not cond:
        fail(msg)
"""Both-states control on reconstructed fixtures: the present-tense instrument
must FIRE on the known-stale M-NN premise and stay SILENT on a premise
verified current in the same pack. Silence on both = detector dead."""
import json

fix_dir = Path(__file__).resolve().parent / "fixtures"
stale = json.loads((fix_dir / "stale-premise.json").read_text(encoding="utf-8"))
current = json.loads((fix_dir / "current-premise.json").read_text(encoding="utf-8"))
doc = load()
resolution = json.loads((REPO / "command-center" / "OPTION-ID-RESOLUTION.json").read_text(encoding="utf-8"))
res_text = json.dumps(resolution).lower()


def fires(premise):
    """Instrument 1 (recorded): open present-tense premise whose subject the
    resolution artifact marks as landed => stale."""
    open_tense = any(t in premise["text"].lower() for t in ("remains open", "is queued", "is still open"))
    subject_landed = premise["subject_token"].lower() in res_text and premise.get("landed_token", "mech-").lower() in res_text
    return bool(open_tense and subject_landed)


need(fires(stale) is True, "instrument did not FIRE on the known-stale premise")
need(fires(current) is False, "instrument FIRED on the verified-current premise")
both = doc.get("both_states") or {}
need(both.get("stale_fired") is True and both.get("current_silent") is True,
     "artifact both_states disagrees with live instrument")
meas = doc.get("measurements") or []
known = next((m for m in meas if m.get("id") == "known-case"), None)
need(known is not None and known.get("fired_ids") == ["P-STALE-MNN-OPEN"],
     "recorded known-case fired_ids mismatch")
need(known.get("silent_ids") == ["P-CURRENT-MECH-REPREFIX"], "recorded silent_ids mismatch")
ok("both states: stale fired, current silent")
