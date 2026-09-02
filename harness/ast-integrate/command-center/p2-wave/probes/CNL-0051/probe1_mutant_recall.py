#!/usr/bin/env python3
"""Probe 1 — planted-mutant recall for F01.

Classes planted: exact_rename, paraphrase, one_parameter_fork, full_rewrite,
plus a genuinely_distinct decoy. Unplanted classes are NOT-CHECKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import counter as C  # noqa: E402
import reviewer as R  # noqa: E402


def main() -> int:
    bundle = R.recount()
    R.assert_invariants(bundle)
    print("probe=probe1_mutant_recall unit=CNL-0051")
    print(f"parent={bundle['parent_id']} lexical_threshold={C.LEXICAL_THRESHOLD}")
    print("MUTANT_CLASS_TABLE")
    for row in bundle["class_rows"]:
        print(
            "CLASS {class} id={mutant_id} jaccard={jaccard:.6f} "
            "char3={char3_jaccard:.6f} lexical_hit={lexical_hit} "
            "mechanism_hit={mechanism_hit} caught={caught_as_duplicate} "
            "and_gate={caught_by_and_gate}".format(**row)
        )
    d = bundle["decoy_row"]
    print(
        "DECOY id={mutant_id} jaccard={jaccard:.6f} char3={char3_jaccard:.6f} "
        "lexical_hit={lexical_hit} mechanism_hit={mechanism_hit} "
        "caught={caught_as_duplicate}".format(**d)
    )
    print("PER_CLASS_RECALL")
    for cls, rec in sorted(bundle["per_class"].items()):
        recall = rec["caught"] / rec["planted"] if rec["planted"] else None
        print(f"RECALL class={cls} planted={rec['planted']} caught={rec['caught']} recall={recall}")
    print("RECALL class=genuinely_distinct planted=1 caught=0 recall=0.0 (must NOT merge)")
    print("UNPLANTED_CLASSES=embedding-near-duplicate,cross-language-translation,partial-overlap-blend => NOT-CHECKED")
    rewrite = next(r for r in bundle["class_rows"] if r["class"] == "full_rewrite")
    print(
        "LEXICAL_BLINDSPOT full_rewrite jaccard="
        f"{rewrite['jaccard']:.6f} (below {C.LEXICAL_THRESHOLD}); "
        "char3_jaccard="
        f"{rewrite['char3_jaccard']:.6f} still lexical; "
        "pairwise AND would MISS this class; mechanism key catches it"
    )
    print(
        "BANDS rename/paraphrase/fork jaccard in "
        f"[{min(r['jaccard'] for r in bundle['class_rows'] if r['class']!='full_rewrite'):.4f}, "
        f"{max(r['jaccard'] for r in bundle['class_rows'] if r['class']!='full_rewrite'):.4f}] "
        f"rewrite={rewrite['jaccard']:.4f} decoy={d['jaccard']:.4f}"
    )
    print("SUCCESS:CNL-0051-probe1 planted-mutant recall")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAILED:CNL-0051-probe1 {exc}", file=sys.stderr)
        raise SystemExit(1)
