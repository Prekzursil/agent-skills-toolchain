"""Named probe 2: gated mojibake detector, parse-first, consumer honesty."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import run_census  # noqa: E402
from common import COMPLETION_SENTINEL, FX_CORRECT, FX_DOUBLE, OUT, UNIT  # noqa: E402
from detector import control_vectors, naive_latin1_repair  # noqa: E402


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if COMPLETION_SENTINEL not in OUT.read_text(encoding="utf-8"):
        return fail("completion_sentinel absent")

    live = run_census()
    s = live["summary"]
    v = control_vectors()
    if not v["production_both_states"]:
        return fail("production detector failed both-states control", v)
    if not v["mutant_killed"]:
        return fail("any-non-ASCII mutant was not killed", v)
    if not v["collision_silent"]:
        return fail("production detector fired on times-yen collision", v)
    if not v["ungated_refuted"]:
        return fail("ungated reversible detector did not demonstrate D1", v)
    repaired = naive_latin1_repair(v["collision"])
    if repaired == v["collision"]:
        return fail("naive latin-1 repair did not mutate the collision")
    if not s["planted_double_decoded_fired"] or FX_DOUBLE not in s["confirmed_mojibake_paths"]:
        return fail("planted double-decoded fixture silent", s["confirmed_mojibake_paths"])
    if not s["planted_correct_silent"] or FX_CORRECT in s["confirmed_mojibake_paths"]:
        return fail("planted correct Unicode was flagged", s["confirmed_mojibake_paths"])
    if s["extension_only_overclaim_paths"]:
        return fail(
            "strict_parser_consumed claimed without product reader",
            s["extension_only_overclaim_paths"],
        )

    art = doc.get("census") or {}
    for key in (
        "confirmed_mojibake_count",
        "confirmed_mojibake_paths",
        "strict_consumed_count",
        "extension_only_overclaim_paths",
    ):
        if art.get(key) != s.get(key):
            return fail(f"artifact/live mismatch {key}", {"art": art.get(key), "live": s.get(key)})

    rec = (doc.get("named_probe_records") or {}).get("probe2") or {}
    if rec.get("confirmed_mojibake_count") != s["confirmed_mojibake_count"]:
        return fail("named_probe_records.probe2 count mismatch", rec)

    out = {
        "probe": "probe2-mojibake",
        "unit_id": UNIT,
        "pass": True,
        "production_both_states": True,
        "mutant_killed": True,
        "collision_silent": True,
        "ungated_refuted": True,
        "naive_latin1_mutates_collision": True,
        "planted_double_decoded_fired": True,
        "planted_correct_silent": True,
        "confirmed_mojibake_count": s["confirmed_mojibake_count"],
        "confirmed_mojibake_paths": s["confirmed_mojibake_paths"],
        "strict_consumed_count": s["strict_consumed_count"],
        "extension_only_overclaim_paths": s["extension_only_overclaim_paths"],
        "artifact_matches_live": True,
        "parse_first": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:AUD-0085-probe2 gated mojibake detector parse-first consumer honesty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
