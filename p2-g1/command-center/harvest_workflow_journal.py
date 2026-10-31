r"""Harvest completed agent results out of a live or stopped workflow journal.

WHY. The owner asked for ONE comprehensive workflow instead of a chain of them, "while maintaining
existing results and validated parts of the existing one and running one". Stopping a running
workflow without harvesting would throw away finished lens work -- six audit lanes here each ran
7-70 minutes. A workflow's return value only materialises if the whole script completes, but every
agent's result is journalled the moment that agent finishes, so the finished work is recoverable even
mid-run.

TWO FIELD NAMES THAT SILENTLY RETURN NOTHING, both learned the hard way:
  * the payload key is `result`, NOT `value` -- reading `value` yields None for every row;
  * the join key is `agentId`; the journal's `key` field is a CONTENT HASH, not a label, so joining
    on it matches nothing and produces a clean empty harvest that reads as "there was nothing there".
This script therefore prints the raw key inventory of the journal it read, so a schema change shows up
as a visible surprise instead of an empty file.

It writes ONE json artifact and never mutates the workflow. Safe to run against a live run.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

SESSION = "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d"
WF_ROOT = (
    Path("C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil")
    / SESSION
    / "subagents"
    / "workflows"
)
OUT_DIR = Path(__file__).resolve().parent / "harvest"


def rows(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a torn tail is expected while the run is live
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: harvest_workflow_journal.py <run-id> [<run-id> ...]")
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grand: dict[str, object] = {}

    for run in argv:
        journal = WF_ROOT / run / "journal.jsonl"
        if not journal.is_file():
            print(f"  {run}: NOT-CHECKED no journal.jsonl")
            continue
        recs = rows(journal)
        keyinv = Counter(k for r in recs for k in r)
        print(f"\n=== {run}: {len(recs)} rows")
        print(f"    key inventory: {dict(keyinv.most_common(12))}")

        harvested = []
        for r in recs:
            res = r.get("result")
            if res in (None, "", {}, []):
                continue
            harvested.append(
                {
                    "agentId": r.get("agentId"),
                    "label": r.get("label") or r.get("name") or "",
                    "phase": r.get("phase") or "",
                    "result": res,
                }
            )
        # Control: rows but no payload. There are TWO causes and conflating them is a detector bug I
        # shipped and hit within the hour -- the tool blamed a schema change when the real answer was
        # "every agent is still running". A journal row is written when an agent STARTS; the `result`
        # key appears only when it FINISHES. So `result` missing from EVERY row is normal for a young
        # run and alarming only if the key is absent from the inventory entirely.
        if recs and not harvested:
            if "result" in keyinv:
                print(
                    f"    NOT-CHECKED:harvest {len(recs)} rows carry a `result` key but all are "
                    f"empty -- agents started and none has finished. Nothing to harvest YET."
                )
                continue
            print(
                f"    NOT-CHECKED:harvest {len(recs)} rows and NO `result` key anywhere. Either no "
                f"agent has finished yet, or the payload key moved -- check the inventory above "
                f"against a run you know completed before concluding the schema changed."
            )
            continue

        sizes = [len(json.dumps(h["result"], ensure_ascii=False)) for h in harvested]
        print(
            f"    harvested {len(harvested)} agent results, {sum(sizes):,} chars total"
        )
        for h, s in zip(harvested, sizes):
            print(f"      {s:>8,}B  {h['label'] or h['agentId']}")
        grand[run] = harvested

    total = sum(len(v) for v in grand.values())
    if not total:
        print("\nNOT-CHECKED:harvest nothing to harvest from any run")
        return 0

    out = OUT_DIR / ("harvest-" + "-".join(argv) + ".json")
    out.write_text(json.dumps(grand, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n  wrote {out} ({out.stat().st_size:,}B, {total} results)")
    print("\nSUCCESS:harvest-workflow-journal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
