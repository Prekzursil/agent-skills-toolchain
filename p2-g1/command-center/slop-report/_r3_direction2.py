"""Sharpen the direction verdict: separate EDITED lines from ADDED-only content.

_r3_direction.py compares line multisets, which cannot distinguish

  H1 -- one line was edited in place (a `replace` opcode: same slot, new text),
  H2 -- each side independently gained content the other never had
        (a `delete` block on one side AND an `insert` block on the other),

and reports BOTH as "two-way". That is the same shape of mistake the fan-out
contract's C4 records, so the sharper claim needs the sharper instrument.

difflib opcodes over the meaningful lines give it directly:
  delete  -> a run present only in the repo-root file
  insert  -> a run present only in the agent-self mirror
  replace -> a run edited in place; direction is genuinely ambiguous

"substantively two-way" = at least one `delete` run AND at least one `insert` run.
A pair whose only opcode is `replace` is an in-place edit, not two-way content.

Run:  python command-center/slop-report/_r3_direction2.py
"""

from __future__ import annotations

import difflib
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = Path(__file__).with_name("_r3_twinsurface.out.json")
OUT = Path(__file__).with_suffix(".out.json")


def lines(rel: str) -> list[str]:
    text = (REPO / rel).read_text(encoding="utf-8")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def opcode_profile(a: list[str], b: list[str]) -> dict:
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    counts = Counter()
    root_only_runs, mirror_only_runs = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        counts[tag] += 1
        if tag == "delete":
            root_only_runs.append(i2 - i1)
        elif tag == "insert":
            mirror_only_runs.append(j2 - j1)
    return {
        "opcodes": dict(counts),
        "root_only_runs": len(root_only_runs),
        "root_only_lines": sum(root_only_runs),
        "mirror_only_runs": len(mirror_only_runs),
        "mirror_only_lines": sum(mirror_only_runs),
    }


def verdict_of(p: dict) -> str:
    if p["root_only_runs"] and p["mirror_only_runs"]:
        return "two-way"
    if p["root_only_runs"]:
        return "root-only-adds"
    if p["mirror_only_runs"]:
        return "mirror-only-adds"
    return "in-place-edit-only"


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = []
    for pair in data["differing_pairs"]:
        prof = opcode_profile(lines(pair["root"]), lines(pair["mirror"]))
        rows.append({"root": pair["root"], "verdict": verdict_of(prof), **prof})

    # ---- controls: the instrument must distinguish the two hypotheses -----
    controls = {}
    base = ["a", "b", "c", "d"]
    # H1 in-place edit only -> must NOT read two-way.
    controls["c1_pure_replace_is_not_two_way"] = (
        verdict_of(opcode_profile(base, ["a", "B", "c", "d"])) == "in-place-edit-only"
    )
    # H2 each side gained its own run -> MUST read two-way.
    controls["c2_real_two_way_reads_two_way"] = (
        verdict_of(opcode_profile(["a", "root1", "b", "c"], ["a", "b", "mirror1", "c"]))
        == "two-way"
    )
    # C3 strict superset on the root side -> root-only-adds, never two-way.
    controls["c3_superset_reads_one_way"] = (
        verdict_of(opcode_profile(["a", "extra", "b"], ["a", "b"])) == "root-only-adds"
    )
    # C4 identical input -> no opcodes at all.
    controls["c4_identical_has_no_opcodes"] = (
        opcode_profile(base, base)["opcodes"] == {}
    )

    tally = Counter(r["verdict"] for r in rows)
    payload = {
        "rev": data["rev"],
        "differing": len(rows),
        "tally": dict(tally),
        "controls": controls,
        "all_controls_pass": all(controls.values()),
        "rows": sorted(rows, key=lambda r: (r["verdict"], r["root"])),
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    for r in payload["rows"]:
        print(
            f"{r['verdict']:>19}  root-only {r['root_only_lines']:>3}l/{r['root_only_runs']}r"
            f"  mirror-only {r['mirror_only_lines']:>3}l/{r['mirror_only_runs']}r  {r['root']}"
        )
    print(f"\ntally={dict(tally)}")
    for k, v in controls.items():
        print(f"  control {k}: {v}")
    if not payload["all_controls_pass"]:
        print("FAILED:r3-direction2 a control did not pass")
        return 1
    print(f"SUCCESS:r3-direction2 -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
