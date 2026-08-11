r"""Print the findings each completed workflow lane returned, from the journal.

The journal records one `result` line per finished agent with its full return value. Reading it
directly means a lane's work is usable the moment it lands, instead of waiting for the whole
workflow -- and it survives the workflow dying, which is the recovery path the tool docs point at.

Join on `agentId`. The journal `key` is a CONTENT HASH, not a label; joining on it silently pairs
the wrong records.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WF = Path(
    "C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil/"
    "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/subagents/workflows"
)


def main(argv: list[str]) -> int:
    run = argv[0] if argv else "wf_4af49ffb-22a"
    journal = WF / run / "journal.jsonl"
    if not journal.exists():
        print(f"FAILED:wf-results no journal at {journal}")
        return 1

    results = []
    for line in journal.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") == "result":
            results.append(rec)

    if not results:
        print("NOT-CHECKED:wf-results journal holds 0 result records (nothing has returned yet)")
        return 2

    print(f"  {len(results)} lane result(s)\n")
    for rec in results:
        # The payload key is `result`, NOT `value`. Reading the wrong key made all 45 records look
        # like None and nearly produced "the agents returned nothing" as a finding.
        val = rec.get("result")
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except ValueError:
                pass
        if not isinstance(val, dict):
            print(f"  --- {rec.get('agentId', '?')[:12]}: non-dict result, {str(val)[:200]}")
            continue
        print(f"  ===== LANE {val.get('lane', rec.get('agentId', '?')[:12])} =====")
        cov = str(val.get("coverage") or "")
        print(f"  COVERAGE: {cov[:400]}")
        for f in val.get("findings") or []:
            print(f"    [{f.get('status', '?'):16}] {str(f.get('claim', ''))[:150]}")
            print(f"        conf: {str(f.get('confidence', ''))[:60]}")
            print(f"        ev  : {str(f.get('evidence', ''))[:200]}")
            if f.get("unverified"):
                print(f"        UNVERIFIED: {str(f['unverified'])[:200]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
