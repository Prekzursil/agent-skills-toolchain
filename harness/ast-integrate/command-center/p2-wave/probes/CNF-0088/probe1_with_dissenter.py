#!/usr/bin/env python3
"""Named probe 1: with-dissenter verbatim survival + planted-defect controls.

Signal: substring location of the injected position plus attribution and
recommendation-token presence. A generic mention without the specific
position must fail this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import survival_verdict  # noqa: E402
from fixtures import DISSENTER_ID, INJECTED_POSITION, TOKEN  # noqa: E402
from synthesis import with_dissenter  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0088-dissent-survival.json"
UNIT = "CNF-0088"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:CNF-0088" not in blob:
        return fail("sentinel absent")

    live = with_dissenter("preserve")
    verdict = survival_verdict(live)
    if not verdict["pass"] or not live.get("completed"):
        return fail("live with-dissenter survival", verdict)

    loc = verdict["location"]
    if INJECTED_POSITION not in live["synthesis_text"]:
        return fail("verbatim position not in live synthesis")
    if loc["verbatim_index"] < 0 or loc["attribution_index"] < 0:
        return fail("location indexes", loc)
    if TOKEN not in live["synthesis_text"]:
        return fail("token missing from synthesis")

    dropped = survival_verdict(with_dissenter("drop"))
    paraphrased = survival_verdict(with_dissenter("paraphrase"))
    generic = survival_verdict(with_dissenter("generic"))
    if dropped["pass"]:
        return fail("drop control silent", dropped)
    if paraphrased["pass"]:
        return fail("paraphrase control silent", paraphrased)
    if generic["pass"]:
        return fail("generic-mention control silent", generic)
    if "dissent-dropped" not in (dropped.get("reasons") or []):
        return fail("drop not classified dissent-dropped", dropped)
    if not any("paraphrased" in r or "generic" in r for r in paraphrased.get("reasons") or []):
        return fail("paraphrase not classified", paraphrased)
    if not generic.get("generic_mention_present"):
        return fail("generic fixture lacked generic mention", generic)

    art_run = None
    for run in doc.get("runs") or []:
        if run.get("id") == "with-dissenter":
            art_run = run
            break
    if not art_run or not art_run.get("completed"):
        return fail("artifact with-dissenter run missing")
    if art_run.get("synthesis_text") != live["synthesis_text"]:
        return fail("artifact synthesis_text != live re-run")
    if INJECTED_POSITION not in art_run["synthesis_text"]:
        return fail("artifact lost verbatim position")
    if f"Attributed to {DISSENTER_ID}" not in art_run["synthesis_text"]:
        return fail("artifact lost attribution")

    located = (doc.get("minority_report_location") or {})
    if located.get("verbatim_index") != loc["verbatim_index"]:
        return fail("artifact location mismatch", located)

    out = {
        "probe": "probe1-with-dissenter",
        "unit_id": UNIT,
        "pass": True,
        "verbatim": True,
        "attributed": True,
        "recommendation_acknowledges": True,
        "token": TOKEN,
        "verbatim_index": loc["verbatim_index"],
        "attribution_index": loc["attribution_index"],
        "negative_controls": {
            "drop_fired": True,
            "paraphrase_fired": True,
            "generic_mention_fired": True,
        },
        "artifact_matches_live": True,
    }
    (HERE / "probe1-with-dissenter.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0088-probe1 with-dissenter verbatim survival")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
