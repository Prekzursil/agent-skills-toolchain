#!/usr/bin/env python3
"""Named probe 2: noise-floor downgrade, two-way recompute, sampling redraw."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recompute as R  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0033-metric-recompute.json"
SCHEMA = REPO / "command-center/schema/benchmark-report.schema.json"
RAW = REPO / "command-center/p2-wave/probes/CNF-0033/fixtures/raw/control_match.json"
AFTER = REPO / "command-center/p2-wave/probes/CNF-0033/fixtures/raw/control_unmeasurable_after.json"
CNF0027 = "command-center/confirmation/CNF-0027-baseline-variance.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0033-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = S.payload_of(doc)
    live_errs = S.iter_errors(doc)
    if live_errs:
        print("FAILED:CNF-0033-probe2 artifact fails overlay schema", live_errs[0].message)
        return 1
    cat_errs = S.catalog_iter_errors(doc)
    if cat_errs:
        print("FAILED:CNF-0033-probe2 artifact fails catalog schema", cat_errs[0].message)
        return 1

    # Sampling-frame redraw: reload the fixture sample and require identity.
    sample = R.load_repetitions(RAW)
    expected = [7.0, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0, 13.0]
    if sample != expected:
        print("FAILED:CNF-0033-probe2 sample redraw mismatch", sample)
        return 1
    after = R.load_repetitions(AFTER)
    if len(sample) != 11 or len(after) != 11:
        print("FAILED:CNF-0033-probe2 n!=11")
        return 1

    tw = R.two_way_median(sample)
    iqr = R.two_way_iqr(sample)
    print(f"two_way_median agree={tw['agree']} a={tw['method_a']['value']} b={tw['method_b']['value']}")
    print(f"two_way_iqr agree={iqr['agree']} a={iqr['method_a']['value']} b={iqr['method_b']['value']}")
    if not tw["agree"] or not iqr["agree"]:
        print("FAILED:CNF-0033-probe2 two-way disagreement")
        return 1
    art_tw = payload.get("control_two_way") or doc.get("control_two_way") or {}
    if art_tw.get("agree") is not True:
        print("FAILED:CNF-0033-probe2 artifact two-way not agree")
        return 1
    if abs(float(art_tw["method_a"]["value"]) - float(tw["method_a"]["value"])) > 1e-12:
        print("FAILED:CNF-0033-probe2 two-way value drift")
        return 1

    floor = float(iqr["method_a"]["value"])
    live = R.evaluate_delta(
        claim_id="control.unmeasurable",
        source="detector-control",
        before_rel="command-center/p2-wave/probes/CNF-0033/fixtures/raw/control_match.json",
        after_rel="command-center/p2-wave/probes/CNF-0033/fixtures/raw/control_unmeasurable_after.json",
        claimed_value=9.8,
        claimed_delta=-0.2,
        precision_decimals=1,
        noise_floor=floor,
        noise_floor_file=CNF0027,
    )
    if live["verdict"] != "UNMEASURABLE":
        print("FAILED:CNF-0033-probe2 unmeasurable verdict", live)
        return 1
    if abs(float(live["delta"])) > floor:
        print("FAILED:CNF-0033-probe2 |delta| exceeds floor", live["delta"], floor)
        return 1
    # Sign of the claimed improvement is negative; still unmeasurable.
    if float(live["delta"]) >= 0:
        print("FAILED:CNF-0033-probe2 expected negative recomputed delta", live["delta"])
        return 1

    by_id = {c["id"]: c for c in S.claims_of(doc)}
    art_u = by_id.get("control.unmeasurable") or {}
    if art_u.get("verdict") != "UNMEASURABLE":
        print("FAILED:CNF-0033-probe2 artifact unmeasurable", art_u)
        return 1

    nf = payload.get("noise_floor") or doc.get("noise_floor") or {}
    if nf.get("present") is True:
        print("FAILED:CNF-0033-probe2 claimed CNF-0027 present")
        return 1
    if CNF0027 not in str(nf.get("missing_file") or nf.get("source") or ""):
        print("FAILED:CNF-0033-probe2 CNF-0027 not named", nf)
        return 1
    if (REPO / CNF0027).is_file():
        print("FAILED:CNF-0033-probe2 CNF-0027 unexpectedly present")
        return 1

    # Mutant: a NOT-CHECKED row without the missing file named must fail schema.
    mutant = copy.deepcopy(doc)
    stripped = False
    for row in S.claims_of(mutant):
        if row.get("verdict") == "NOT-CHECKED" and "missing_raw_file" in row:
            del row["missing_raw_file"]
            stripped = True
            break
    if not stripped:
        print("FAILED:CNF-0033-probe2 no NOT-CHECKED row to strip")
        return 1
    merrs = S.iter_errors(mutant)
    if not merrs:
        print("FAILED:CNF-0033-probe2 mutant without missing_raw_file was accepted")
        return 1
    print(f"mutant_rejected={True} errs={len(merrs)}")

    print(
        f"floor={floor} delta={live['delta']} unmeasurable=True "
        f"sample_n={len(sample)} cnf0027_missing=True"
    )
    print("SUCCESS:CNF-0033-probe2 noise-floor two-way sampling-redraw")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
