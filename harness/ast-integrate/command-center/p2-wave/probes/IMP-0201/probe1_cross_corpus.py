#!/usr/bin/env python3
"""Named probe 1: cross-corpus comparison refused; same-corpus permitted (both-states).

Bad state: a run whose corpus_version differs from the frozen baseline.
  Production compare_to_baseline must refuse with CROSS_CORPUS_REFUSED.
Good state: the same per-case rows under the baseline's corpus_version.
  Production compare_to_baseline must proceed.

Load-bearing check: the known-broken sibling compare_ignoring_corpus_for_control
would permit the bad pair. That proves the corpus gate is what stops the
comparison, not an accidental case-set or score mismatch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.evals.baseline import (  # noqa: E402
    REASON_CROSS_CORPUS,
    REASON_SPEC_MISMATCH,
    compare_ignoring_corpus_for_control,
    compare_to_baseline,
    load_json,
)
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0201.json"
FIX = HERE / "fixtures"


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:IMP-0201-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:2000])
    return 1


def main() -> int:
    S.write_fixtures(FIX)
    baseline = load_json(FIX / "baseline-certified.json")
    same = load_json(FIX / "run-same-corpus.json")
    cross = load_json(FIX / "run-cross-corpus.json")
    spec_mis = load_json(FIX / "run-spec-mismatch.json")

    # Rebuild in memory and require byte-stable identity fields vs fixtures.
    mem_base = S.certified_baseline()
    if mem_base["corpus_version"] != baseline["corpus_version"]:
        return _fail("fixture drift corpus_version")
    if mem_base["per_case_rows"] != baseline["per_case_rows"]:
        return _fail("fixture drift per_case_rows")

    good = compare_to_baseline(same, baseline)
    bad = compare_to_baseline(cross, baseline)
    ungated = compare_ignoring_corpus_for_control(cross, baseline)
    spec_bad = compare_to_baseline(spec_mis, baseline)

    report = {
        "probe": "probe1-cross-corpus",
        "unit_id": "IMP-0201",
        "same_corpus_ok": bool(good.get("ok")),
        "same_corpus_refused": bool(good.get("refused")),
        "same_corpus_n": good.get("n_cases"),
        "same_corpus_mean_delta": good.get("mean_delta"),
        "cross_corpus_ok": bool(bad.get("ok")),
        "cross_corpus_refused": bool(bad.get("refused")),
        "cross_corpus_reason": bad.get("reason"),
        "ungated_would_permit_cross_corpus": bool(ungated.get("ok")),
        "spec_mismatch_reason": spec_bad.get("reason"),
        "pass": False,
    }

    if not good.get("ok") or good.get("refused"):
        return _fail("same-corpus comparison was not permitted", good)
    if good.get("n_cases") != 4:
        return _fail(f"same-corpus n_cases={good.get('n_cases')} want=4", good)
    if good.get("summary_consulted"):
        return _fail("same-corpus path consulted summary", good)
    if bad.get("ok") or not bad.get("refused"):
        return _fail("cross-corpus comparison was not refused", bad)
    if bad.get("reason") != REASON_CROSS_CORPUS:
        return _fail(
            f"cross-corpus reason {bad.get('reason')!r} want {REASON_CROSS_CORPUS}",
            bad,
        )
    if "cross-corpus" not in str(bad.get("detail") or "").lower() and "corpus" not in str(
        bad.get("detail") or ""
    ).lower():
        return _fail("cross-corpus refusal detail does not name corpus", bad)
    if not ungated.get("ok"):
        return _fail(
            "known-broken sibling did not permit the cross-corpus pair; "
            "both-states control is inert",
            ungated,
        )
    if spec_bad.get("reason") != REASON_SPEC_MISMATCH:
        return _fail("spec mismatch was not refused with named reason", spec_bad)

    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0201":
        return _fail(f"receipt unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"receipt self-declared {doc.get('state')}")
    if "SUCCESS:IMP-0201" not in text:
        return _fail("sentinel absent")
    if REASON_CROSS_CORPUS not in text:
        return _fail("receipt does not name CROSS_CORPUS_REFUSED")

    report["pass"] = True
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "same_corpus_permitted=True "
        f"cross_corpus_refused=True reason={REASON_CROSS_CORPUS} "
        "ungated_would_permit=True"
    )
    print("SUCCESS:IMP-0201-probe1 cross-corpus refused, same-corpus permitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
