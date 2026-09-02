#!/usr/bin/env python3
"""Probe 2: version-string trap + mutation controls + NOT-CHECKED completeness.

Independent of probe1's refresh-on/off pair. A reviewer who only re-reads the
receipt has verified nothing; this re-runs the mutations and requires each
one to turn the gate red.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import drill as D  # noqa: E402
from packages import NEW_VERSION, OLD_BEHAVIOUR  # noqa: E402

ART = REPO / "command-center/receipts/REL-0020.json"


def main() -> int:
    trap = D.version_string_trap()
    print(
        "trap version={0} behaviour={1} hit={2} holds={3}".format(
            trap["version"], trap["behaviour"], trap["hit"], trap["trap_holds"]
        )
    )
    if not trap["trap_holds"]:
        print("FAILED:REL-0020-probe2 version trap did not hold")
        return 1
    if trap["version"] != NEW_VERSION or trap["behaviour"] != OLD_BEHAVIOUR:
        print("FAILED:REL-0020-probe2 expected new version + old behaviour")
        return 1
    if trap["version_equals_behaviour"]:
        print("FAILED:REL-0020-probe2 version string is being used as behaviour")
        return 1

    partial = D.partial_refresh_still_masked()
    print(
        "partial_refresh cleared={0} behaviour={1} hit={2} still_masked={3}".format(
            partial["cleared"],
            partial["behaviour"],
            partial["hit"],
            partial["still_masked"],
        )
    )
    if not partial["still_masked"]:
        print("FAILED:REL-0020-probe2 bytecode-only refresh did not stay red")
        return 1
    if partial["hit"] != "unpacked-user-cache":
        print("FAILED:REL-0020-probe2 expected unpacked-user-cache to mask after partial refresh")
        return 1

    off = D.poisoned_without_refresh()
    if not off["perceives_defect"]:
        print("FAILED:REL-0020-probe2 refresh-disabled mutation did not stay red")
        return 1

    iso = D.isolation_self_check()
    print(
        "isolation owner_home={0} raises={1}".format(
            iso["owner_home"], iso["client_on_owner_home_raises"]
        )
    )
    if not iso["client_on_owner_home_raises"]:
        print("FAILED:REL-0020-probe2 Client(Path.home()) did not raise")
        return 1

    if not ART.is_file():
        print("FAILED:REL-0020-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = D.receipt_honest(doc)
    print(f"receipt_honest={ok} {why}")
    if not ok:
        print("FAILED:REL-0020-probe2 receipt_honest failed")
        return 1

    mutant = copy.deepcopy(doc)
    locs = mutant.get("locations") or []
    stripped = [r for r in locs if r.get("status") != "NOT-CHECKED"]
    if len(stripped) == len(locs):
        print("FAILED:REL-0020-probe2 receipt had no NOT-CHECKED row to strip")
        return 1
    mutant["locations"] = stripped
    mutant["evidence"]["not_checked"] = []
    mok, mwhy = D.receipt_honest(mutant)
    print(f"mutant_omit_not_checked ok={mok} {mwhy}")
    if mok:
        print("FAILED:REL-0020-probe2 omitting NOT-CHECKED was accepted")
        return 1

    mutant2 = copy.deepcopy(doc)
    mutant2["evidence"]["behavioural_new"] = mutant2["evidence"]["version_new"]
    m2ok, m2why = D.receipt_honest(mutant2)
    print(f"mutant_version_as_behaviour ok={m2ok} {m2why}")
    if m2ok:
        print("FAILED:REL-0020-probe2 version-string-as-behaviour was accepted")
        return 1

    inv_ids = [r["id"] for r in (doc.get("locations") or [])]
    print(f"inventory_ids={inv_ids}")
    if "windows-localappdata-plugin-cache" not in inv_ids:
        print("FAILED:REL-0020-probe2 windows location omitted from receipt")
        return 1
    if "owner-live-home-cache" not in inv_ids:
        print("FAILED:REL-0020-probe2 owner-live location omitted from receipt")
        return 1
    if "product-platform-plugin-cache" not in inv_ids:
        print("FAILED:REL-0020-probe2 product cache.py location omitted from receipt")
        return 1

    ctrl = doc.get("controls") or {}
    if ctrl.get("partial_refresh_bytecode_only_still_masked") is not True:
        print("FAILED:REL-0020-probe2 receipt missing partial-refresh mutation")
        return 1
    rev = doc.get("reviewer") or {}
    if rev.get("mutation_controls_rerun") is not True or rev.get("independent") is not True:
        print("FAILED:REL-0020-probe2 reviewer did not record mutation re-run")
        return 1
    if "SUCCESS:REL-0020" not in ART.read_text(encoding="utf-8"):
        print("FAILED:REL-0020-probe2 sentinel absent")
        return 1
    print("SUCCESS:REL-0020-probe2 version trap and mutation controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
