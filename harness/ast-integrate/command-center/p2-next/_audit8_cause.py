"""AUDIT probe 8: WHY does re-running vendor_satisfiability.py now yield 47/4 instead of 41/10?

Measured: the 6 AUD units flip SATISFIABLE_NOW -> RAIL_BLOCKED. Import the builder's own module
and ask it, per AUD unit, which rule fires and on which text -- against the PRE-EDIT blob
(899ff779^) and the POST-EDIT blob (HEAD). Two states, same instrument.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "command-center" / "p2-next" / "vendor_satisfiability.py"

spec = importlib.util.spec_from_file_location("vs", MOD)
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)
print("module attrs of interest:", [a for a in dir(vs) if not a.startswith("_")][:30])

AUD = {
    "AUD-0006": "command-center/audit/AUD-0006-uncommitted-work-census.json",
    "AUD-0020": "command-center/audit/AUD-0020-python-dep-inventory.json",
    "AUD-0030": "command-center/audit/AUD-0030-import-graph-cycles.json",
}
TOK = re.compile(
    r"cross[-_ ]?vendor|cross[-_ ]?model|\bopenai\b|\bcodex\b|gpt-?5", re.I
)


def blob(rev, path):
    r = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(r.stdout) if r.returncode == 0 else None


for uid, path in AUD.items():
    print(f"\n================ {uid} ================")
    for rev in ("899ff779^", "HEAD"):
        o = blob(rev, path)
        if o is None:
            print(f"  {rev}: absent")
            continue
        f = o.get("failure") or {}
        rv = o.get("reviewer") or {}
        bo = f.get("blocked_on") or ""
        notes = rv.get("notes") or ""
        print(f"  --- {rev}")
        print(
            f"      blocked_on token hits : {sorted(set(m.group(0).lower() for m in TOK.finditer(bo)))}"
        )
        print(
            f"      reviewer.notes hits   : {sorted(set(m.group(0).lower() for m in TOK.finditer(notes)))}"
        )
        for m in TOK.finditer(notes):
            s = max(0, m.start() - 90)
            print(f"        ...{notes[s : m.end() + 90]!r}")
            break
