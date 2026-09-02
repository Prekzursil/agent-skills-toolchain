#!/usr/bin/env python3
"""Named probe 2: strict-parse shipped manifests; planted unknown is rejected
and must never reach the emitted artifact.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from emit_policy import PLANTED_UNKNOWN, emit_marketplace, emit_plugin  # noqa: E402
from read_shim import read_manifest  # noqa: E402
from strict_parser import parse, rejection_text  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0459.json"
PLUGIN = REPO / ".claude-plugin" / "plugin.json"
MARKET = REPO / ".claude-plugin" / "marketplace.json"
SENTINEL = "SENTINEL:IMP-0459:MANIFEST-STRICT-CLEAN"
A2_PLUGIN = (
    REPO
    / "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/typed/plugin.json"
)


def main() -> int:
    if not ART.is_file() or SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0459-probe2 receipt/sentinel")
        return 1
    if json.loads(ART.read_text(encoding="utf-8")).get("state") in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0459-probe2 receipt blocked")
        return 1

    plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
    market = json.loads(MARKET.read_text(encoding="utf-8"))
    p_ok = parse("plugin", plugin)
    m_ok = parse("marketplace", market)
    print(f"shipped plugin ok={p_ok['ok']} marketplace ok={m_ok['ok']}")
    if not p_ok["ok"] or not m_ok["ok"]:
        print("FAILED:IMP-0459-probe2 shipped manifest failed strict-parse")
        print(p_ok["rejection_messages"], m_ok["rejection_messages"])
        return 1
    shipped_text = PLUGIN.read_text(encoding="utf-8") + MARKET.read_text(encoding="utf-8")
    for banned in (PLANTED_UNKNOWN, "_generated", '"rules"'):
        if banned in shipped_text:
            print(f"FAILED:IMP-0459-probe2 banned {banned} in shipped bytes")
            return 1

    planted = copy.deepcopy(plugin)
    planted[PLANTED_UNKNOWN] = "detector-control"
    planted_parse = parse("plugin", planted)
    msg = rejection_text(planted_parse)
    print(f"planted parse ok={planted_parse['ok']} msg={msg}")
    if planted_parse["ok"] or PLANTED_UNKNOWN not in msg:
        print("FAILED:IMP-0459-probe2 planted unknown was not rejected by name")
        return 1

    emitted = emit_plugin(planted)
    if PLANTED_UNKNOWN in emitted or PLANTED_UNKNOWN in json.dumps(emitted):
        print("FAILED:IMP-0459-probe2 planted field reached emitted artifact")
        return 1
    if not parse("plugin", emitted)["ok"]:
        print("FAILED:IMP-0459-probe2 emit of planted source was not strict-clean")
        return 1
    print("emit stripped planted; emitted keys=" + ",".join(sorted(emitted)))

    a2 = json.loads(A2_PLUGIN.read_text(encoding="utf-8"))
    a2_direct = parse("plugin", a2)
    print(f"a2 source strict ok={a2_direct['ok']} msg={rejection_text(a2_direct)}")
    if a2_direct["ok"]:
        print("FAILED:IMP-0459-probe2 A2 source with _generated/rules was accepted")
        return 1
    shim = read_manifest("plugin", a2)
    extras = set(shim["extra_keys"])
    print(f"read-shim extras={sorted(extras)} strict_ok={shim['strict_ok']}")
    if extras != {"_generated", "rules"} or not shim["strict_ok"]:
        print("FAILED:IMP-0459-probe2 read shim did not peel A2 unknown fields")
        return 1

    both = parse("plugin", {"name": "ok", "version": "1.0.0"})
    if not both["ok"]:
        print("FAILED:IMP-0459-probe2 both-states known field rejected")
        return 1

    market_planted = copy.deepcopy(market)
    market_planted[PLANTED_UNKNOWN] = "detector-control"
    mp = parse("marketplace", market_planted)
    if mp["ok"] or PLANTED_UNKNOWN not in rejection_text(mp):
        print("FAILED:IMP-0459-probe2 marketplace planted not named")
        return 1
    market_emitted = emit_marketplace(market_planted)
    if PLANTED_UNKNOWN in json.dumps(market_emitted):
        print("FAILED:IMP-0459-probe2 marketplace planted leaked")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-emit-plant",
                "unit_id": "IMP-0459",
                "shipped_strict_ok": True,
                "planted_rejected": True,
                "planted_absent_from_emit": True,
                "read_shim_peeled_a2": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0459-probe2 emit policy and planted unknown control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
