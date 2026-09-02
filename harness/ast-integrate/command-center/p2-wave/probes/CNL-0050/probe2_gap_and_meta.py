#!/usr/bin/env python3
"""Probe 2: independent spec-vs-corpus gap + META-COMPOSITION coverage.

Reviewer path: method B comma-split must yield the same 58 cards as method A.
Gap is set-subtracted from catalog-quoted spec names, not copied from the brief.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as N  # noqa: E402
import meta_trees as M  # noqa: E402

OUT = (
    HERE.parents[3]
    / "command-center"
    / "design"
    / "council"
    / "CNL-0050-protocol-composition-primitives-phase-ordering-and-the-spe.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0050-probe2 {msg}")
    return 1


def main() -> int:
    report = N.gap_report()
    cards = report["cards"]
    meta = M.compile_all()
    print(
        f"cards method_a={cards['n_method_a']} method_b={cards['n_method_b']} "
        f"agree={cards['methods_agree']} library_present={cards['library_file_present']}"
    )
    print(f"spec_named n={report['spec']['n']} names={[x['name'] for x in report['spec']['names']]}")
    print(f"gap_conservative n={report['n_gap_conservative']} {report['gap_conservative']}")
    print(f"gap_substring n={report['n_gap_substring']} {report['gap_substring']}")
    print(
        f"meta n={meta['n']} expressible={meta['n_expressible']} "
        f"gap={meta['n_gap']} compile_fail={meta['n_compile_fail']}"
    )
    print(f"inherited_from_brief={report['inherited_from_unit_brief']}")

    if cards["n_method_a"] != 58 or cards["n_method_b"] != 58:
        return fail("card count is not 58 on both methods")
    if not cards["methods_agree"]:
        return fail("method A regex and method B comma-split disagree")
    if cards["library_file_present"]:
        return fail("library file appeared; census must switch to reading it")
    if report["inherited_from_unit_brief"]:
        return fail("gap marked as inherited from the brief")

    gap_l = {x.lower() for x in report["gap_conservative"]}
    if "negotiation" not in gap_l:
        return fail("independent gap missed negotiation")
    if not any("steelman" in x for x in gap_l):
        return fail("independent gap missed steelman")
    # The brief is a first pass, not the census. Extra gaps are allowed.

    if meta["n"] != 7:
        return fail(f"META-COMPOSITION n={meta['n']} want 7")
    if not meta["all_expressible_or_gapped"]:
        return fail("a META-COMPOSITION card is neither EXPRESSIBLE nor GAP")
    if meta["n_compile_fail"]:
        return fail("a META-COMPOSITION tree failed to compile")
    if set(meta["primitives"]) != {"sequence", "splice", "nest", "repeat-until"}:
        return fail(f"primitives drifted: {meta['primitives']}")

    if not OUT.is_file():
        return fail(f"artifact missing {OUT}")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    art_gap = doc.get("spec_vs_corpus_gap") or {}
    live = list(report["gap_conservative"])
    claimed = list(art_gap.get("gap_conservative") or [])
    if claimed != live:
        return fail(f"artifact gap {claimed} != live {live}")
    if art_gap.get("inherited_from_unit_brief") is not False:
        return fail("artifact claims inherited gap")
    if "SUCCESS:CNL-0050" not in OUT.read_text(encoding="utf-8"):
        return fail("sentinel missing from artifact text")

    print("reviewer_recount cards=58 gap_n=" + str(report["n_gap_conservative"]))
    print("SUCCESS:CNL-0050-probe2 independent gap and META-COMPOSITION coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
