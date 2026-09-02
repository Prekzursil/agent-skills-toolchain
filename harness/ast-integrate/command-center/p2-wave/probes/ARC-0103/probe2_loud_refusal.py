#!/usr/bin/env python3
"""Probe 2: incompatible pair raises; field counts prove it is not a silent drop."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import golden as G  # noqa: E402
import negotiate as N  # noqa: E402

REPORT = REPO / G.OUT_REL


def main() -> int:
    catalog = G.load_catalog()
    control = G.loud_refusal_control(catalog)

    if not control.get("raises_on_incompatible"):
        print("FAILED:ARC-0103-probe2 live (2,1) did not refuse")
        return 1
    if not control.get("accepts_previous_on_current"):
        print("FAILED:ARC-0103-probe2 (1,2) did not ACCEPT")
        return 1
    if not control.get("silent_drops_work_units"):
        print("FAILED:ARC-0103-probe2 silent reader did not drop work_units")
        return 1

    live = control["live_pair"]
    silent = live["silent_partial_read"]
    refused = live["negotiation"]
    producer_n = int(silent["producer_field_count"])
    consumed_n = int(silent["consumed_field_count"])
    if producer_n <= consumed_n:
        print(
            f"FAILED:ARC-0103-probe2 field counts producer={producer_n} "
            f"consumed={consumed_n} (need producer > consumed)"
        )
        return 1
    if int(silent["producer_work_units"]) <= 0:
        print("FAILED:ARC-0103-probe2 detector silent: zero work_units on live catalog")
        return 1
    if int(silent["consumed_work_units"]) != 0:
        print(
            "FAILED:ARC-0103-probe2 silent reader kept work_units="
            f"{silent['consumed_work_units']}"
        )
        return 1
    if "work_units" not in (refused.get("dropped_fields") or []):
        print(f"FAILED:ARC-0103-probe2 refusal dropped_fields={refused.get('dropped_fields')}")
        return 1
    if int(refused.get("producer_field_count") or 0) != producer_n:
        print(
            "FAILED:ARC-0103-probe2 refusal producer_field_count "
            f"{refused.get('producer_field_count')} != live {producer_n}"
        )
        return 1
    if int(refused.get("consumer_field_count") or 0) != consumed_n:
        print(
            "FAILED:ARC-0103-probe2 refusal consumer_field_count "
            f"{refused.get('consumer_field_count')} != silent {consumed_n}"
        )
        return 1

    # Planted both-states: incompatible toy must refuse; silent read shrinks fields.
    planted = control["planted_incompatible"]
    if planted["negotiation"].get("status") != "REFUSE":
        print("FAILED:ARC-0103-probe2 planted pair did not REFUSE")
        return 1
    if int(planted["producer_field_count"]) <= int(planted["silent_field_count"]):
        print(
            "FAILED:ARC-0103-probe2 planted field counts "
            f"producer={planted['producer_field_count']} "
            f"silent={planted['silent_field_count']}"
        )
        return 1

    # Compatible direction must not raise.
    v1 = N.catalog_v1_projection(catalog)
    try:
        accepted = N.negotiate(v1, 2, G.consumer_fields_for(2, catalog), N.CATALOG_CLASS)
    except N.VersionRefusal as exc:
        print(f"FAILED:ARC-0103-probe2 (1,2) raised {exc}")
        return 1
    if accepted.get("status") != "ACCEPT":
        print(f"FAILED:ARC-0103-probe2 (1,2) status={accepted.get('status')}")
        return 1

    # Encoding control: CRLF is not a data defect.
    lf_doc = b'{"id":"enc-control","n":1}\n'
    crlf_doc = lf_doc.replace(b"\n", b"\r\n")
    data_doc = b'{"id":"enc-control","n":2}\n'
    if G.classify_surfaces(lf_doc, lf_doc) != "identical":
        print("FAILED:ARC-0103-probe2 identical misclassified")
        return 1
    if G.classify_surfaces(crlf_doc, lf_doc) != "crlf-only":
        print("FAILED:ARC-0103-probe2 CRLF misclassified as data")
        return 1
    if G.classify_surfaces(data_doc, lf_doc) != "data-divergence":
        print("FAILED:ARC-0103-probe2 data mutation silent")
        return 1

    if REPORT.is_file():
        doc = json.loads(REPORT.read_text(encoding="utf-8"))
        body = G.report_body(doc)
        reported = body.get("loud_refusal_control") or {}
        if reported.get("raises_on_incompatible") is not True:
            print("FAILED:ARC-0103-probe2 report raises_on_incompatible false")
            return 1
        if reported.get("field_count_delta", 0) != control["field_count_delta"]:
            print(
                "FAILED:ARC-0103-probe2 stale field_count_delta "
                f"doc={reported.get('field_count_delta')} live={control['field_count_delta']}"
            )
            return 1
        enc = body.get("encoding_control") or {}
        if enc.get("crlf_not_misread_as_data") is not True:
            print("FAILED:ARC-0103-probe2 report encoding flag false")
            return 1
        if "SUCCESS:ARC-0103" not in json.dumps(doc):
            print("FAILED:ARC-0103-probe2 sentinel absent from report")
            return 1

    print(
        f"refuse_loud=True producer_fields={producer_n} consumed_fields={consumed_n} "
        f"dropped_work_units={silent['producer_work_units']} "
        f"field_count_delta={control['field_count_delta']} "
        f"previous_schema_accept=True planted_refuse=True"
    )
    print("SUCCESS:ARC-0103-probe2 loud-refusal field-count control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
