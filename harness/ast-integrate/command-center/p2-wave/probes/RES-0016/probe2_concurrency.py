#!/usr/bin/env python3
"""Probe 2: concurrency ceiling twice + detector control + two-shell re-run.

Known-broken state: ultracode exemption lets the 21st spawn succeed. The real
cap must still refuse with the verbatim documented error.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from docs_extract import extract as extract_docs  # noqa: E402
from measure import (  # noqa: E402
    concurrency_twice,
    detector_control_concurrent,
    slot_reuse_after_finish,
    two_shell_concurrency,
)
from payload import detector_fired, measurements_of  # noqa: E402
from runtime import CONCURRENT_REFUSAL, DEFAULT_CONCURRENT  # noqa: E402

ART = REPO / "command-center/research/RES-0016.json"
SENTINEL = (
    "SUCCESS:RES-0016 in the receipt AND a measured depth limit, an inheritance "
    "verdict backed by two contrasting spawns, and a twice-reproduced concurrency ceiling"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0016-probe2 {msg}")
    return 1


def main() -> int:
    docs = extract_docs()
    conc = concurrency_twice()
    det = detector_control_concurrent()
    reuse = slot_reuse_after_finish()
    shells = two_shell_concurrency()
    print(
        json.dumps(
            {
                "probe": "probe2-concurrency",
                "docs_concurrent": docs["concurrent_default"],
                "ceiling": conc["ceiling"],
                "reproduced_twice": conc["reproduced_twice"],
                "verbatim_refusal": conc["verbatim_refusal"],
                "detector_control_fired": det["fired"],
                "two_shells": shells["reproduced_across_shells"],
                "slot_reuse": reuse["spawn_after_finish_ok"],
            },
            sort_keys=True,
        )
    )
    if docs["concurrent_default"] != DEFAULT_CONCURRENT:
        return fail("docs extract concurrent != 20")
    if docs["concurrent_refusal"] != CONCURRENT_REFUSAL:
        return fail("docs extract refusal string")
    if not conc["reproduced_twice"]:
        return fail("ceiling not reproduced twice")
    if conc["ceiling"] != docs["concurrent_default"]:
        return fail("runtime ceiling != docs extract")
    if conc["verbatim_refusal"] != CONCURRENT_REFUSAL:
        return fail("refusal not verbatim")
    if not det["fired"]:
        return fail("ultracode mutant did not discriminate from the real cap")
    if reuse["third_while_full"] != CONCURRENT_REFUSAL:
        return fail("slot-full refusal")
    if not reuse["spawn_after_finish_ok"]:
        return fail("slot reuse after finish failed")
    if not shells["reproduced_across_shells"]:
        return fail("bash vs sh ceilings diverged")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("catalog completion sentinel absent")
    meas = measurements_of(doc)
    if int(meas.get("concurrency_ceiling") or -1) != conc["ceiling"]:
        return fail("artifact concurrency_ceiling drift")
    if meas.get("concurrency_reproduced_twice") is not True:
        return fail("artifact twice-reproduced flag")
    if (meas.get("concurrency_refusal") or {}).get("message") != CONCURRENT_REFUSAL:
        return fail("artifact concurrency refusal drift")
    if detector_fired(doc) is not True:
        return fail("reviewer did not record detector control")
    print(
        "SUCCESS:RES-0016-probe2 ceiling="
        f"{conc['ceiling']} twice=True detector={det['fired']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
