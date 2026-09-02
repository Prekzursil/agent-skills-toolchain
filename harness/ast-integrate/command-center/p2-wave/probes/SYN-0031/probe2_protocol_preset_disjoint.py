#!/usr/bin/env python3
"""Probe 2: protocol and preset id sets are disjoint; regexes are cross-silent.

Planted overlap must be detected. Blind sum / max of the two lists is refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

OUT = REPO / X.OUT_REL
SCHEMA = REPO / X.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0031-probe2 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact absent")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    errs = X.schema_errors(doc, REPO)
    if errs:
        return fail("schema " + errs[0])

    live = X.measure_live(REPO)
    domain = X.domain_from_artifact(doc)
    art = domain["protocol_preset_disjointness"] or {}
    live_d = live["disjoint"]
    if art.get("empty_intersection") is not True:
        return fail(f"artifact intersection not empty {art.get('intersection_ids')}")
    if live_d["empty_intersection"] is not True:
        return fail(f"live intersection {live_d['intersection_ids']}")
    if art.get("did_not_sum_blind") is not True:
        return fail("did_not_sum_blind missing")
    if art.get("did_not_take_max") is not True:
        return fail("did_not_take_max missing")

    floors = {row["id"]: row for row in domain["floors"]}
    proto_n = floors["council_protocols"]["this_count"]
    preset_n = floors["presets"]["this_count"]
    if proto_n == live_d["sum_would_have_been"] and preset_n > 0:
        return fail("protocols this_count looks like a blind sum")
    if proto_n == live_d["max_would_have_been"] and preset_n not in (0, proto_n):
        return fail("protocols this_count looks like max-of-two-lists")
    print(
        f"live protocols={proto_n} presets={preset_n} "
        f"intersection={live_d['intersection_ids']} "
        f"sum_would_have_been={live_d['sum_would_have_been']} "
        f"max_would_have_been={live_d['max_would_have_been']}"
    )

    good = HERE / "fixtures/corpus-good/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    good_proto = X.json_array_ids(good, ["protocols"])
    good_preset = X.json_array_ids(good, ["presets"])
    good_d = X.protocol_preset_disjoint(good_proto, good_preset)
    if not good_d["empty_intersection"]:
        return fail(f"good fixture overlap {good_d['intersection_ids']}")
    print(f"fixture-good disjoint proto={good_proto} preset={good_preset}")

    overlap = HERE / "fixtures/planted-overlap/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    ov_d = X.protocol_preset_disjoint(
        X.json_array_ids(overlap, ["protocols"]),
        X.json_array_ids(overlap, ["presets"]),
    )
    if ov_d["empty_intersection"]:
        return fail("planted overlap was silent")
    if "SHARED-1" not in ov_d["intersection_ids"]:
        return fail(f"planted overlap ids {ov_d['intersection_ids']}")
    print(f"planted-overlap fired intersection={ov_d['intersection_ids']}")

    md = (
        HERE / "fixtures/corpus-good/12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
    ).read_text(encoding="utf-8")
    silence = X.regex_cross_silence(md, md)
    if not silence["protocol_silent_on_preset_items"]:
        return fail(f"protocol regex hit presets {silence['protocol_hits_on_presets']}")
    if not silence["preset_silent_on_protocol_items"]:
        return fail(f"preset regex hit protocols {silence['preset_hits_on_protocols']}")
    art_s = domain["regex_cross_silence"] or {}
    if art_s.get("protocol_silent_on_preset_items") is not True:
        return fail("artifact protocol_silent_on_preset_items")
    if art_s.get("preset_silent_on_protocol_items") is not True:
        return fail("artifact preset_silent_on_protocol_items")
    proto_hits = X.PROTOCOL_HEADING_RE.findall(md)
    preset_hits = X.PRESET_HEADING_RE.findall(md)
    if proto_hits != ["PROT-001", "PROT-002", "PROT-003", "PROT-004"]:
        return fail(f"protocol heading ids {proto_hits}")
    if preset_hits != ["PSET-001", "PSET-002", "PSET-003", "PSET-004"]:
        return fail(f"preset heading ids {preset_hits}")
    print(
        f"cross-silence protocol_re={silence['protocol_regex']} "
        f"preset_re={silence['preset_regex']} "
        f"proto_ids={proto_hits} preset_ids={preset_hits}"
    )
    print("SUCCESS:SYN-0031-probe2 protocol-preset disjoint and cross-silence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
