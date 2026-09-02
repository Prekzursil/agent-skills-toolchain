#!/usr/bin/env python3
"""Probe 1: known-present harness refs + MECH false-positive control.

Known-present: all 20 deep-research M-<harness> references across both
duplicated trees (16 files) must be found.
False-positive: a MECH-NN token must NOT be reported as a bare ambiguous M-NN.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import harness_census, mech_false_positive, option_partition  # noqa: E402

ART = REPO / "command-center/receipts/CC-0021.json"
SENTINEL = "SUCCESS:CC-0021"


def main() -> int:
    h = harness_census()
    fp = mech_false_positive()
    part = option_partition()
    print(
        json.dumps(
            {
                "harness_census": {k: h[k] for k in ("refs", "files", "want_refs", "want_files", "ok")},
                "mech_false_positive": {
                    k: fp[k]
                    for k in ("bare_m_hits", "mech_hits", "mech_decl_ids", "ok")
                },
                "option_partition": {
                    "option_n": len(part["option"]),
                    "mech_n": len(part["mech"]),
                    "intersection_n": len(part["intersection"]),
                    "option_only_n": len(part["option_only"]),
                    "mech_only_n": len(part["mech_only"]),
                    "ok": part["ok"],
                },
            },
            sort_keys=True,
        )
    )
    if not h["ok"]:
        print(
            f"FAILED:CC-0021-probe1 harness refs={h['refs']} files={h['files']} "
            f"want=20/16 sample={h['sample']}"
        )
        return 1
    if not fp["ok"]:
        print(
            f"FAILED:CC-0021-probe1 MECH false-positive bare_m={fp['bare_m_hits']} "
            f"decl={fp['mech_decl_ids']} sample={fp['sample_bare_m']}"
        )
        return 1
    if not part["ok"]:
        print(
            f"FAILED:CC-0021-probe1 partition opt={len(part['option'])} "
            f"mech={len(part['mech'])} inter={len(part['intersection'])}"
        )
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CC-0021-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CC-0021-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CC-0021-probe1 sentinel absent")
        return 1
    print(
        f"harness={h['refs']}/{h['files']} mech_bare_m={fp['bare_m_hits']} "
        f"partition=33/38/31/7/2"
    )
    print("SUCCESS:CC-0021-probe1 known-present and MECH false-positive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
