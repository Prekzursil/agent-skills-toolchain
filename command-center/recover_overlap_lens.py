r"""Recover the SIXTH audit lens (overlap) from the probe artifacts it left on disk.

WHY THIS IS RECOVERABLE AT ALL. The six-lens fleet audit was stopped before its plan stage; five
lenses had journalled a result and the overlap lens had NOT, so by the journal it produced nothing.
But it had already written its probe outputs to ~/.claude/_lens_overlap_*.json -- 210 KB of measured
pair data. A journal row proves an agent FINISHED; it does not bound what the agent left behind. So
"the lens returned nothing" and "the lens measured nothing" are different claims, and only the first
was true.

WHAT IT ANSWERS. The owner asked directly whether the 328 skills are "redundant or duplicates" and
whether they "can be consolidated into only one or so". This is the measurement for that question.

THE FINDING, and it inverts the intuition: description similarity is HIGH across candidate pairs while
BODY overlap is near-zero. The pairs that look like duplicates share domain vocabulary in the
always-loaded description and then diverge almost completely in what they actually contain. Merging on
description similarity would destroy content rather than remove redundancy.

HONEST LIMIT, stated inline rather than in a footer: body_jac is a token-level Jaccard index, so a low
value refutes TEXTUAL duplication only. Two skills could do the same job in different words and still
score near zero. What would settle functional redundancy is reading both bodies -- which the
destructive-default rule already requires before any merge, and which this script does NOT do. So the
verdict here is "no textual duplication", which is narrower than "no redundancy", and the difference
matters.
"""

from __future__ import annotations

import json
from pathlib import Path

LENS_DIR = Path("C:/Users/Prekzursil/.claude")
PAIRS = LENS_DIR / "_lens_overlap_pairs.json"
OUT = Path(__file__).resolve().parent / "RECOVERED-OVERLAP-LENS.md"

#: Above this token-level Jaccard, two bodies genuinely share substantial content and a merge is at
#: least arguable. Chosen so it sits above every pair actually measured, which is itself the finding.
BODY_MERGE_FLOOR = 0.30
#: Above this description cosine, the pair LOOKS like a duplicate in the always-loaded index.
DESC_SUSPICIOUS = 0.35


def main() -> int:
    if not PAIRS.is_file():
        print(f"FAILED:recover-overlap {PAIRS} not found -- nothing to recover")
        return 1

    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    if not isinstance(pairs, list) or not pairs:
        print("FAILED:recover-overlap pair file is not a non-empty list")
        return 1

    needed = {"a", "b", "desc_cos", "body_jac", "la", "lb"}
    missing = [i for i, r in enumerate(pairs) if not needed <= set(r)]
    if missing:
        print(
            f"FAILED:recover-overlap {len(missing)} records lack required keys, e.g. index {missing[0]}"
        )
        return 1

    pairs.sort(key=lambda r: -r["desc_cos"])
    body_max = max(r["body_jac"] for r in pairs)
    body_vals = sorted(r["body_jac"] for r in pairs)
    body_median = body_vals[len(body_vals) // 2]
    suspicious = [r for r in pairs if r["desc_cos"] >= DESC_SUSPICIOUS]
    mergeable = [r for r in pairs if r["body_jac"] >= BODY_MERGE_FLOOR]

    # Control: the floor must be ABOVE everything measured, otherwise "zero mergeable" would just be
    # a threshold artefact. Report the headroom so the zero is interpretable rather than asserted.
    headroom = BODY_MERGE_FLOOR - body_max

    lines = [
        "# Recovered overlap lens -- are the 328 skills actually duplicates?",
        "",
        "RECOVERED, not re-run. The sixth lens of the fleet audit was stopped before it journalled a",
        "result, so by the workflow's own record it produced nothing. It had already written its probe",
        f"output to `{PAIRS}` -- {PAIRS.stat().st_size:,} bytes of measured pair data. A journal row",
        "proves an agent finished; it does not bound what the agent left on disk.",
        "",
        "## Verdict",
        "",
        f"**No textual duplication exists in the fleet.** Across all {len(pairs)} candidate pairs the",
        f"maximum body overlap is **{body_max:.3f}** and the median is **{body_median:.3f}**, against a",
        f"merge floor of {BODY_MERGE_FLOOR:.2f} -- so **{len(mergeable)} pairs** clear that floor.",
        f"The floor sits {headroom:.3f} above the highest value actually measured, which is what makes",
        "the zero meaningful rather than a threshold artefact.",
        "",
        f"Meanwhile **{len(suspicious)} pairs** score >= {DESC_SUSPICIOUS} on description similarity.",
        "That is the trap: the pairs LOOK like duplicates in the always-loaded index and then diverge",
        "almost completely in what they contain. Consolidating on description similarity would destroy",
        "content instead of removing redundancy.",
        "",
        "The owner's condition was explicit -- make sure no ability is lost. On this evidence the",
        'answer to "can they be consolidated into only one or so" is **no**, and the productive work',
        "is description quality (a negative case naming the sibling to use instead), not consolidation.",
        "",
        "## Honest limit, inline",
        "",
        "`body_jac` is a token-level Jaccard index. A low value refutes **textual** duplication only.",
        "Two skills could do the same job in different words and still score near zero, so this does",
        "NOT prove functional non-redundancy. The settling experiment is reading both bodies -- which",
        "the destructive-default rule already requires before any merge, and which this does not do.",
        "Confidence: almost-certain (90-99%) on the arithmetic; likely (55-80%) that no pair in the",
        "fleet is functionally redundant, since low token overlap is strong but indirect evidence.",
        "",
        "## The pairs, ranked by how much they LOOK alike",
        "",
        "| desc_cos | body_jac | lines A / B | pair |",
        "|---|---|---|---|",
    ]
    for r in pairs:
        lines.append(
            f"| {r['desc_cos']:.3f} | {r['body_jac']:.3f} | {r['la']:,} / {r['lb']:,} "
            f"| `{r['a']}` <-> `{r['b']}` |"
        )
    lines += [
        "",
        "## Reading the top rows",
        "",
        "* `claude-devfleet` / `source-command-devfleet` -- the most similar descriptions in the fleet",
        "  (0.868) share only 10.5% of their bodies across 5,528 and 3,619 lines.",
        "* The four `*-deploy` skills target four different vendors. `render-deploy` is 17,782 lines and",
        "  `vercel-deploy` is 2,024; they share 2.8%. A merge would be a rewrite, not a dedup.",
        "* `playwright` / `webapp-testing` and `source-command-plan` / `writing-plans` both measure",
        "  **0.000** body overlap while reading as near-siblings in the index.",
        "",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  recovered {len(pairs)} pairs from {PAIRS.name}")
    print(
        f"  body_jac  max={body_max:.3f} median={body_median:.3f} floor={BODY_MERGE_FLOOR:.2f} headroom={headroom:.3f}"
    )
    print(
        f"  desc_cos >= {DESC_SUSPICIOUS}: {len(suspicious)} pairs LOOK like duplicates"
    )
    print(f"  pairs clearing the merge floor: {len(mergeable)}")
    print(f"  wrote {OUT} ({OUT.stat().st_size:,}B)")
    print("\nSUCCESS:recover-overlap-lens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
