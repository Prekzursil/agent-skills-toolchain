#!/usr/bin/env python3
"""Probe 1: indistinguishability — zero-dial-diff seats are DUPLICATE_SEAT."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import participant as P  # noqa: E402
import v1_seat as V  # noqa: E402
import offline_validate as OV  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
)
SENTINEL = "SUCCESS:CNL-0005"


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:CNL-0005-probe1 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    good = P.find_duplicates(P.good_roster())
    print(
        f"good_roster seats={good['seat_count']} "
        f"identities={good['distinct_identity_count']} fired={good['fired']}"
    )
    if good["fired"] or good["seat_count"] != 3 or good["distinct_identity_count"] != 3:
        return fail("good_roster must be silent with 3 distinct identities", good)

    dup = P.find_duplicates(P.zero_dial_diff_pair())
    print(
        f"zero_dial_diff fired={dup['fired']} findings={dup['findings']}"
    )
    if not dup["fired"]:
        return fail("zero-dial-diff pair was silently accepted")
    if not any(f["code"] == "DUPLICATE_SEAT" for f in dup["findings"]):
        return fail("expected DUPLICATE_SEAT code", dup)
    if dup["distinct_identity_count"] != 1:
        return fail("zero-dial-diff must collapse to 1 identity", dup)

    derived = P.find_duplicates(P.vendor_derived_pair())
    print(
        f"vendor_derived fired={derived['fired']} "
        f"identities={derived['distinct_identity_count']}"
    )
    if not derived["fired"]:
        return fail("omitted unique vendor vs explicit vendor must be one identity")

    distinct = P.find_duplicates(P.distinct_model_pair())
    print(
        f"distinct_model fired={distinct['fired']} "
        f"identities={distinct['distinct_identity_count']}"
    )
    if distinct["fired"] or distinct["distinct_identity_count"] != 2:
        return fail("model-differing pair must be silent with 2 identities", distinct)

    try:
        P.fill(P.ambiguous_vendor_seat())
        return fail("llama-3.1-70b without vendor must raise VENDOR_AMBIGUOUS")
    except P.DescriptorError as exc:
        print(f"ambiguous_vendor code={exc.code}")
        if exc.code != "VENDOR_AMBIGUOUS":
            return fail("wrong code for ambiguous vendor", exc.code)

    try:
        P.fill(P.invalid_missing_model())
        return fail("missing model must raise")
    except P.DescriptorError as exc:
        print(f"missing_model code={exc.code}")
        if exc.code != "MODEL_REQUIRED":
            return fail("wrong code for missing model", exc.code)

    # Optional dials may be omitted without collapsing seats that still
    # differ on a required dial (scribe vs chair).
    omitted = P.unspecified_optionals(P.scribe_gemini())
    print(f"scribe_omitted_optionals={omitted}")
    if set(omitted) != set(P.OPTIONAL_DIALS):
        return fail("scribe fixture should omit every optional dial", omitted)

    line = P.verbatim_negative_control(dup)
    print(f"negative_control_verbatim={line}")
    gap = V.field_by_field()
    print(
        f"v1_seat_present={gap['v1']['present']} "
        f"preset_carries={gap['carried_on_disk_preset_roles']} "
        f"preset_lacks={gap['lacking_on_disk_preset_roles']}"
    )

    payload = OV.report_payload(doc)
    claimed = payload.get("indistinguishability") or {}
    if claimed.get("zero_dial_diff_fires") is not True:
        return fail("artifact indistinguishability.zero_dial_diff_fires is not true")
    if claimed.get("distinct_model_silent") is not True:
        return fail("artifact indistinguishability.distinct_model_silent is not true")

    print(
        json.dumps(
            {
                "good_silent": True,
                "zero_dial_diff_fires": True,
                "vendor_derived_collapses": True,
                "distinct_model_silent": True,
                "ambiguous_vendor_rejected": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0005-probe1 indistinguishability duplicate-seat detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
