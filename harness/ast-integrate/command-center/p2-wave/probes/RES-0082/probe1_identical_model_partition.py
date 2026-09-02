#!/usr/bin/env python3
"""Probe 1: identical-model partition question is answered, and E3 cannot promote.

Both-states: the live record must pass; dropping the verdict or promoting the
E3 anonymity headline must fail the same checker.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from checks import (  # noqa: E402
    ARTIFACT,
    UNIT,
    check_record,
    load_artifact,
    mutant_drop_verdict,
    mutant_promote_e3,
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ARTIFACT.is_file():
        return fail(f"artifact missing {ARTIFACT}")
    doc = load_artifact()
    errs = check_record(doc)
    if errs:
        return fail("live record: " + "; ".join(errs[:8]))

    ident = doc["identical_model_partition"]
    if ident.get("verdict") != "NOT-ESTABLISHED":
        return fail(f"expected NOT-ESTABLISHED, got {ident.get('verdict')!r}")
    if "arXiv:2607.01661" not in str(ident.get("doi_or_arxiv")):
        return fail("identical-model citation missing InfoDelphi arXiv")

    drop_errs = check_record(mutant_drop_verdict(doc))
    if not drop_errs:
        return fail("control: dropping the verdict still passed")
    promo_errs = check_record(mutant_promote_e3(doc))
    if not promo_errs:
        return fail("control: promoting the E3 headline still passed")

    e3 = [m for m in doc["mechanisms"] if m.get("evidence_tier") == "E3"]
    if not e3 or e3[0].get("promoted") is True:
        return fail("E3 control row missing or promoted")

    payload = {
        "pass": True,
        "probe": "probe1-identical-model-partition",
        "unit_id": UNIT,
        "verdict": ident["verdict"],
        "citation": ident.get("doi_or_arxiv"),
        "drop_verdict_errors": drop_errs[:4],
        "promote_e3_errors": promo_errs[:4],
        "promoted_count": sum(1 for m in doc["mechanisms"] if m.get("promoted")),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "both-states: live NOT-ESTABLISHED+citation PASS; "
        f"drop-verdict FAIL ({drop_errs[0]}); "
        f"promote-E3 FAIL ({promo_errs[0]})"
    )
    print(f"SUCCESS:{UNIT}-probe1 identical-model partition answered with citation or NOT-ESTABLISHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
