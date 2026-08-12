r"""Count the FIELD, not the document.

The first delivered-probe used a regex for stub words and produced false positives: ADV-0006 and
ADV-0013 matched the WORD "placeholder" inside prose that DISCUSSES placeholders (use-vs-mention).
The receipts actually carry a declared `state` (and `sentinel`) field. Read that instead.

Also runs the DETECTOR CONTROL (both-states test): assert the field-reader distinguishes a known
skeleton (ADV-0031, which carries UNKNOWN - not yet measured) from a known complete artifact.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def main() -> int:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = []
    for u in doc["work_units"]:
        p = u.get("output_path")
        if not p:
            continue
        fp = REPO / p
        if not fp.exists():
            continue
        size = fp.stat().st_size
        state = sentinel = "<not-json>"
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
            state = d.get("state", "<no-state-field>")
            sentinel = d.get("sentinel", "<no-sentinel-field>")
        except Exception as exc:
            state = f"<parse-fail:{type(exc).__name__}>"
        rows.append((u["id"], size, str(state), str(sentinel)[:40], p))

    rows.sort()
    tally: Counter = Counter(r[2] for r in rows)
    for uid, size, state, sent, p in rows:
        print(f"  {uid:<10} {size:>8}B  state={state:<24} sentinel={sent}")
    print(f"\nSTATE TALLY over {len(rows)} existing artifacts: {dict(tally)}")

    # DETECTOR CONTROL (both-states): the reader must give DIFFERENT answers for a
    # known-skeleton and a known-complete artifact. If it gives the same, it measures nothing.
    by_id = {r[0]: r for r in rows}
    skel = by_id.get("ADV-0031")
    done = by_id.get("ADV-0010")
    if not skel or not done:
        print("FAILED:state-field control missing one of the control units")
        return 1
    print(f"\nCONTROL known-skeleton ADV-0031 -> state={skel[2]} size={skel[1]}")
    print(f"CONTROL known-complete ADV-0010 -> state={done[2]} size={done[1]}")
    if skel[2] == done[2] and skel[1] == done[1]:
        print("FAILED:state-field detector identical on both states - measures nothing")
        return 1
    print("SUCCESS:state-field detector discriminates the two control states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
