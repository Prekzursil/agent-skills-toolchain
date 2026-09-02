"""Triage the forge's OWN failures: a fusion that emits an invalid document is a forge bug.

The pair search reported two rejection classes that are NOT legitimate verdicts:
``fused workflow fails the DSL gate`` and ``does not decompose back``. Both mean the forge
produced a broken artifact, so they must be separated from real rejections and fixed. This probe
enumerates them with the actual schema/semantic errors so the cause is read, not guessed.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foundry import bench, forge, registry  # noqa: E402


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    cands = [c for c in registry.load_dsl_candidates() if c.dsl_doc]
    cands.sort(key=lambda c: c.id)
    cands = cands[:limit]
    cases = list(bench.DEFAULT_CASES)

    schema_bad: list[dict] = []
    sem_bad: list[dict] = []
    decomp_bad: list[dict] = []
    expected_conflicts: list[dict] = []
    err_hist: Counter = Counter()
    sem_hist: Counter = Counter()

    from wfdsl import semantics

    for i, a in enumerate(cands):
        for b in cands[i + 1 :]:
            fusion = forge.fuse(
                a.dsl_doc, b.dsl_doc, strategy="best-of-breed", cases=cases
            )
            r = bench.benchmark(fusion.doc, cases)
            if not r.schema_valid:
                for e in r.validator_errors:
                    err_hist[e[:110]] += 1
                if len(schema_bad) < 4:
                    schema_bad.append(
                        {
                            "base": fusion.base_id,
                            "donor": fusion.donor_id,
                            "errors": r.validator_errors[:4],
                        }
                    )
            if r.semantic_violations:
                rules = semantics.check_workflow(fusion.doc)
                detail = [
                    {"rule": ru.rule, "violations": ru.violations[:3]}
                    for ru in rules
                    if ru.severity == "violation" and ru.violations
                ]
                # A DSL-SEM-011 violation that the fusion ALREADY recorded as a tool_policy
                # conflict is correct behaviour, not a forge bug: one source denies a tool the
                # other uses, and the merge kept the stricter posture. Counting that as a defect
                # would make this probe flag the right answer as wrong.
                declared = {
                    c["id"]
                    for c in fusion.conflicts
                    if c.get("namespace") == "tool_policy"
                }
                explained = bool(declared) and all(
                    d["rule"] == "DSL-SEM-011"
                    and all(
                        any(tok in v[1] for tok in declared) for v in d["violations"]
                    )
                    for d in detail
                )
                for d in detail:
                    sem_hist[("EXPECTED " if explained else "") + d["rule"]] += 1
                if explained:
                    expected_conflicts.append(
                        {
                            "base": fusion.base_id,
                            "donor": fusion.donor_id,
                            "denied_tools": sorted(declared),
                        }
                    )
                elif len(sem_bad) < 4:
                    sem_bad.append(
                        {
                            "base": fusion.base_id,
                            "donor": fusion.donor_id,
                            "detail": detail,
                        }
                    )
            dec = forge.decompose(
                fusion.doc,
                {
                    str(a.dsl_doc.get("id")): a.dsl_doc,
                    str(b.dsl_doc.get("id")): b.dsl_doc,
                },
            )
            if (
                dec.get("roundtrip", {}).get("verdict") != "CONFIRMED"
                and len(decomp_bad) < 4
            ):
                decomp_bad.append(
                    {
                        "base": fusion.base_id,
                        "donor": fusion.donor_id,
                        "roundtrip": dec.get("roundtrip"),
                        "unattributed": dec.get("unattributed_stages"),
                    }
                )

    out = {
        "pairs": len(cands) * (len(cands) - 1) // 2,
        "forge_bugs": {
            "schema_invalid_examples": schema_bad,
            "schema_error_histogram": dict(err_hist.most_common(10)),
            "unexplained_semantic_violations": sem_bad,
            "decomposition_failure_examples": decomp_bad,
        },
        "expected_refusals": {
            "note": (
                "these fusions are INVALID ON PURPOSE: one source denies a tool the other uses "
                "and the merge kept the stricter posture rather than weakening it to make the "
                "fusion pass. Correct behaviour, reported so it is never mistaken for a bug."
            ),
            "count": len(expected_conflicts),
            "examples": expected_conflicts[:5],
        },
        "semantic_rule_histogram": dict(sem_hist.most_common(10)),
    }
    print(json.dumps(out, indent=2, default=str))
    clean = not schema_bad and not sem_bad and not decomp_bad
    print(f"{'SUCCESS' if clean else 'FAILED'}:forge-selfdefects")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
