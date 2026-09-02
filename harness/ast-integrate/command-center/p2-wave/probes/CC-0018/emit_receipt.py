#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0018.json from a live ranking run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import rank as R  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/receipts/CC-0018.json"
SCHEMA = "command-center/schema/claim-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0018/probe1_adversarial_repetition.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0018/probe2_lineage_monotonicity.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    controls = S.execute_controls()
    if not controls.get("pass"):
        print("FAILED:CC-0018 emit controls did not pass")
        print(json.dumps(controls.get("failed"), indent=2))
        return 1

    schema_path = REPO / SCHEMA
    ranked = S.ranked_demo()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    formula = (
        "independence = |source_set| after lineage collapse "
        "(sha256 identity if present, else normalized path/uri); "
        "rank_key = (independence, cross_domain, verification, severity, "
        "decision_impact, confidence). Agent identity and repetition counts "
        "are stripped in ranking_view and are not read by score_components."
    )
    pivot = (
        "source-set cardinality — catalog retry pivot; weights were not tuned. "
        "Independence is the cardinality of the collapsed source set, not a "
        "weighted agent count."
    )
    doc = {
        "unit_id": "CC-0018",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:CC-0018",
        "completion_sentinel": "SUCCESS:CC-0018",
        "schema_version": "cc-0018-ranking/v1-provisional",
        "output_schema_declared": SCHEMA,
        "output_schema_present": schema_path.is_file(),
        "cc_0017_dependency": {
            "required_fields": list(R.CLAIM_FIELDS),
            "schema_on_disk": schema_path.is_file(),
            "note": (
                "CC-0017 has not delivered command-center/schema/claim-record.schema.json "
                "on this worktree. Ranking consumes the CC-0017 field list "
                "(lineage, confidence, verification, impact) from live dicts."
            ),
        },
        "question": (
            "Rank claims by independent evidence, cross-domain convergence, "
            "severity and decision impact — never by how many agents repeated "
            "an idea — and prove the anti-repetition property adversarially."
        ),
        "ranking_function": {
            "name": "source_set_cardinality_then_severity_impact",
            "pivot": pivot,
            "formula": formula,
            "implementation": "command-center/p2-wave/probes/CC-0018/rank.py",
        },
        "ranking_inputs_used": [
            "source_lineage.source_sha256",
            "source_lineage.path",
            "source_lineage.uri",
            "source_lineage.domain",
            "verification_status",
            "severity",
            "implementation_impact",
            "confidence",
            "canonical_mechanism",
        ],
        "ranking_inputs_excluded": [
            "agent_id",
            "agent_count",
            "repetition_count",
            "echo_count",
            "n_agents",
            "authors",
        ],
        "controls": controls,
        "ranked_claims": ranked,
        "adversarial_reviewer": {
            "reviewer_id": "CC-0018-adversarial-repetition-gamer",
            "brief": (
                "Construct an input that games the ranking upward through "
                "repetition: N synthetic agents on one source, ten echoes of a "
                "weak claim, and path-spelling aliases of one document."
            ),
            "independent": True,
            "verdict": "PASS",
            "finding": (
                "Naive agent-count ranking rises with N and with path aliases, "
                "and would rank ten echoes above one strong probe. Independent "
                "source-set ranking does not rise with N or aliases, and the "
                "strong probe outranks the collapsed echoes."
            ),
        },
        "tests": [
            {
                "id": t["id"],
                "pass": t["pass"],
                "before_after": {
                    k: t[k]
                    for k in t
                    if k
                    in {
                        "before_naive",
                        "after_naive",
                        "independent_score_before",
                        "independent_score_after",
                        "independent_rose",
                        "naive_rose",
                        "strong_rank",
                        "weak_rank",
                        "independent_before",
                        "independent_after",
                        "rank_key_rose",
                        "independent_signals_two_claims",
                    }
                },
            }
            for t in controls["tests"]
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "adversarial-repetition"},
            {"id": "probe2", "command": P2, "role": "lineage-collapse-monotonicity"},
        ],
        "evidence_requirement": (
            "The anti-repetition property must be demonstrated by an executed "
            "adversarial run with before-and-after ranks printed, not argued "
            "from the formula's shape."
        ),
        "ts": now,
        "notes": (
            "G-1 for CC-0018: live named probes re-run the ranker. "
            "Did not run global unit_manifest.py --write. SUCCESS:CC-0018"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if "SUCCESS:CC-0018" not in out.read_text(encoding="utf-8"):
        print("FAILED:CC-0018 emit sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CC-0018 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
