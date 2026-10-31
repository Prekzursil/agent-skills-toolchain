r"""Read a harvested workflow result set and print what each lane actually FOUND.

The point of harvesting is defeated if the findings are only ever passed on as a file PATH. A
1.5-million-token, two-hour audit condensed to 122 KB is worth reading directly -- and the owner
called this out: multiple lanes were tangled and the research was at risk of being carried forward
as a citation rather than as knowledge.

Prints, per lane: the lens name, its coverage statement, and every finding with its action, targets,
evidence, what capability the action would cost, and its confidence band. Sorted so destructive
recommendations (MERGE / RETIRE) come first, because those are the ones that need a human decision
before anything is deleted.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HARVEST_DIR = Path(__file__).resolve().parent / "harvest"
#: MERGE/RETIRE destroy capability; surface them first. Lower sorts earlier.
ACTION_RANK = {
    "RETIRE": 0,
    "MERGE": 1,
    "FIX": 2,
    "ADD": 3,
    "UPGRADE": 4,
    "KEEP": 5,
    "NO-ACTION": 6,
}


def clip(s: object, n: int) -> str:
    t = " ".join(str(s or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def main(argv: list[str]) -> int:
    name = argv[0] if argv else "harvest-wf_18aa91e4-3c1.json"
    detail = "--full" in argv
    path = HARVEST_DIR / name
    if not path.is_file():
        avail = sorted(p.name for p in HARVEST_DIR.glob("*.json"))
        print(f"FAILED:read-harvest {path} not found; available: {avail}")
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    actions: Counter[str] = Counter()
    lenses, total = [], 0

    for run, results in data.items():
        print(f"\n########## {run}: {len(results)} lanes ##########")
        for r in results:
            res = r.get("result")
            if isinstance(res, str):
                # A schema-less lane returns plain text; show its head rather than dropping it.
                print(f"\n=== (text lane {r.get('agentId')}) {len(res):,} chars")
                print("    " + clip(res, 600))
                continue
            if not isinstance(res, dict):
                continue
            lens = res.get("lens") or r.get("label") or r.get("agentId")
            lenses.append(str(lens))
            findings = res.get("findings") or []
            total += len(findings)
            print(f"\n=== LENS {lens}  ({len(findings)} findings)")
            print(f"    coverage: {clip(res.get('coverage'), 400)}")
            ordered = sorted(
                findings, key=lambda f: ACTION_RANK.get(str(f.get("action")), 9)
            )
            for f in ordered:
                act = str(f.get("action", "?"))
                actions[act] += 1
                print(f"    [{act:9}] {clip(f.get('title'), 110)}")
                if f.get("targets"):
                    print(f"                targets : {clip(f.get('targets'), 160)}")
                print(
                    f"                evidence: {clip(f.get('evidence'), 900 if detail else 300)}"
                )
                if str(f.get("capability_at_risk") or "").strip():
                    print(
                        f"                AT RISK : {clip(f.get('capability_at_risk'), 300)}"
                    )
                print(f"                conf    : {clip(f.get('confidence'), 130)}")
                if detail and str(f.get("unverified") or "").strip():
                    print(f"                UNVERIF : {clip(f.get('unverified'), 400)}")

    print(f"\n########## {len(lenses)} lanes, {total} findings")
    print(f"  lenses present : {sorted(lenses)}")
    print(f"  action mix     : {dict(actions.most_common())}")
    destructive = actions.get("MERGE", 0) + actions.get("RETIRE", 0)
    print(
        f"  DESTRUCTIVE    : {destructive} (never acted on without reading both bodies)"
    )
    print("\nSUCCESS:read-harvest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
