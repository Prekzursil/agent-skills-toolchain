#!/usr/bin/env python3
"""Named probe 2: detector controls, derived from raw fetches before the artifact conclusion.

1. HTTP 200 + quote absent => FAILED citation, not reachable-success.
2. Fetched instruction-shaped text is recorded, never executed.
3. Deliberately wrong quote is reported absent (matcher is not matching everything).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0062-citation-liveness.json"


def main() -> int:
    # Re-derive from raw source. Do not read the artifact conclusion first.
    srv = E.start_fixture_server()
    try:
        live = E.fetch_url(f"{srv.base}/live-ok.html")
        missing_page = E.fetch_url(f"{srv.base}/quote-absent.html")
        untrusted = E.fetch_url(f"{srv.base}/untrusted.html")

        live_quote = E.locate_quote(live.body, E.LIVE_QUOTE)
        wrong = E.locate_quote(live.body, E.WRONG_QUOTE)
        absent_of_live = E.locate_quote(missing_page.body, E.LIVE_QUOTE)
        untrusted_quote = E.locate_quote(untrusted.body, E.UNTRUSTED_QUOTE)
        instr = E.instruction_shaped_spans(untrusted.body)

        naive_wrong = E.naive_reachable_is_enough(live.http_status, E.WRONG_QUOTE, live.body)
        naive_absent = E.naive_reachable_is_enough(
            missing_page.http_status, E.LIVE_QUOTE, missing_page.body
        )
        real_wrong_absent = not wrong["present"]
        real_200_absent_failed = (
            missing_page.http_status == 200 and not absent_of_live["present"]
        )

        if not isinstance(untrusted.body, E.UntrustedText):
            print("FAILED:CNF-0062-probe2 body is not UntrustedText")
            return 1
        try:
            untrusted.body("run")  # type: ignore[misc]
            print("FAILED:CNF-0062-probe2 UntrustedText was callable")
            return 1
        except TypeError:
            pass

        if live.http_status != 200 or not live_quote["present"]:
            print("FAILED:CNF-0062-probe2 live page missing the real quote")
            return 1
        if not real_wrong_absent:
            print("FAILED:CNF-0062-probe2 matcher accepted the deliberately wrong quote")
            return 1
        if not real_200_absent_failed:
            print("FAILED:CNF-0062-probe2 200-absent was not detected as quote-not-found")
            return 1
        if not naive_wrong or not naive_absent:
            print("FAILED:CNF-0062-probe2 naive control itself did not fire")
            return 1
        if not (real_wrong_absent and real_200_absent_failed and naive_wrong and naive_absent):
            print("FAILED:CNF-0062-probe2 matcher collapsed into naive reachable-pass")
            return 1
        if not untrusted_quote["present"] or not instr:
            print("FAILED:CNF-0062-probe2 untrusted page missing quote or instruction spans")
            return 1
        if "Ignore previous instructions" not in untrusted.body.as_searchable():
            print("FAILED:CNF-0062-probe2 instruction-shaped text not on fixture")
            return 1
    finally:
        srv.close()

    # Only after independent measurement: confirm the artifact recorded the same controls.
    if not ART.is_file():
        print("FAILED:CNF-0062-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0062-probe2 artifact self-declared", doc.get("state"))
        return 1
    det = SC.detector_of(doc)
    report = SC.report_of(doc)
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    wrong_absent = bool(
        doc.get("wrong_quote_reported_absent")
        or report.get("wrong_quote_reported_absent")
        or det.get("wrong_quote_reported_absent")
        or ext.get("wrong_quote_reported_absent")
    )
    if not wrong_absent:
        print("FAILED:CNF-0062-probe2 artifact omitted wrong_quote_reported_absent")
        return 1
    if det.get("wrong_quote_reported_absent") is not True:
        print("FAILED:CNF-0062-probe2 evidence.wrong_quote_reported_absent")
        return 1
    if det.get("http_200_quote_absent_is_failed_citation") is not True:
        print("FAILED:CNF-0062-probe2 evidence 200-absent flag")
        return 1
    if det.get("control_quote_present") is not False:
        print("FAILED:CNF-0062-probe2 artifact says control quote was present")
        return 1
    if det.get("absent_200_verdict") != "FAILED":
        print("FAILED:CNF-0062-probe2 artifact 200-absent verdict", det.get("absent_200_verdict"))
        return 1
    if "SUCCESS:CNF-0062 emitted only when" not in json.dumps(doc):
        print("FAILED:CNF-0062-probe2 sentinel absent")
        return 1

    by = {c["id"]: c for c in SC.citations_of(doc)}
    art_control = by.get("CONTROL-WRONG-QUOTE") or {}
    art_absent = by.get("CITE-200-ABSENT") or {}
    if art_control.get("quote_present") is not False:
        print("FAILED:CNF-0062-probe2 citation row quote still present")
        return 1
    if art_absent.get("classification") != "quote-not-found":
        print("FAILED:CNF-0062-probe2 200-absent classification", art_absent.get("classification"))
        return 1

    out = {
        "probe": "probe2-controls",
        "unit_id": "CNF-0062",
        "pass": True,
        "wrong_quote_reported_absent": True,
        "http_200_quote_absent_is_failed_citation": True,
        "naive_would_pass_wrong_quote": naive_wrong,
        "naive_would_pass_200_absent": naive_absent,
        "instruction_shaped_recorded": len(instr),
        "fetched_body_executed": False,
        "reviewer_rederived_before_conclusion": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "wrong_quote_absent=True 200_absent_failed=True "
        "untrusted_recorded_not_executed=True naive_would_pass=True"
    )
    print("SUCCESS:CNF-0062-probe2 detector controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
