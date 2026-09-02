#!/usr/bin/env python3
"""Probe 2: lineage collapse, monotonicity, and ranking-input hygiene.

Independence is source-set cardinality. Adding a genuinely independent
corroborating probe must raise the rank. Agent/count fields must be absent
from the scorer.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import rank as R  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/CC-0018.json"
FORBIDDEN = (
    "agent_count",
    "repetition_count",
    "echo_count",
    "n_agents",
    "agent_id",
    "authors",
)


def _fail(msg: str) -> int:
    print(f"FAILED:CC-0018-probe2 {msg}")
    return 1


def main() -> int:
    live = S.execute_controls()
    coll = next(t for t in live["tests"] if t["id"] == "lineage-collapse-same-source-document")
    mono = next(t for t in live["tests"] if t["id"] == "monotonicity-independent-corroboration")

    print("CC-0018 PROBE2 LINEAGE COLLAPSE AND MONOTONICITY")
    print(
        f"LINEAGE COLLAPSE two_claims={coll['independent_signals_two_claims']} "
        f"merged={coll['independent_signals_merged']} "
        f"one_claim_two_rows={coll['independent_signals_one_claim_two_rows']} "
        f"paths={coll['paths']}"
    )
    print(
        f"MONOTONICITY BEFORE independent={mono['independent_before']} "
        f"sort_key={mono['before_sort_key']}"
    )
    print(
        f"MONOTONICITY AFTER  independent={mono['independent_after']} "
        f"sort_key={mono['after_sort_key']} rose={mono['rank_key_rose']}"
    )

    if not coll.get("pass"):
        return _fail("same source document counted as more than one independent signal")
    if not mono.get("pass"):
        return _fail("adding an independent corroborating probe did not raise rank")

    src = "\n".join(
        [
            inspect.getsource(R.ranking_view),
            inspect.getsource(R.score_components),
            inspect.getsource(R.sort_key),
            inspect.getsource(R.source_identity),
        ]
    )
    hits = [tok for tok in FORBIDDEN if tok in src]
    print(f"SCORER_FORBIDDEN_TOKENS hits={hits or []}")
    if hits:
        return _fail(f"scorer source mentions forbidden inputs {hits}")

    view = R.ranking_view(
        {
            "claim_id": "x",
            "agent_count": 99,
            "repetition_count": 99,
            "source_lineage": [
                {"agent_id": "echo", "path": "docs/a.md", "source_sha256": "d" * 64}
            ],
            "verification_status": "CONFIRMED",
            "severity": "high",
            "implementation_impact": "critical",
            "confidence": "almost_certain",
        }
    )
    if "agent_count" in view or "repetition_count" in view:
        return _fail("ranking_view leaked count fields")
    lineage = view.get("source_lineage") or []
    if lineage and "agent_id" in lineage[0]:
        return _fail("ranking_view leaked agent_id")

    if not ART.is_file():
        return _fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CC-0018" not in json.dumps(doc):
        return _fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    excluded = doc.get("ranking_inputs_excluded") or []
    for tok in ("agent_count", "repetition_count", "agent_id"):
        if tok not in excluded:
            return _fail(f"receipt did not exclude {tok}")
    print("SUCCESS:CC-0018-probe2 lineage collapse and monotonicity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
