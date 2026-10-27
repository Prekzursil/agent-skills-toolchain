"""Receipts: reviewer null -> NOT-REVIEWED object (admission requires object)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "_p2shard20-w2"))
import _shard20_lib as L  # noqa: E402

REVIEWER = {
    "reviewer_id": "pending-independent-adversarial-reviewer",
    "verdict": "NOT-REVIEWED",
    "independent": False,
    "notes": ("Builder-authored receipt. State is BLOCKED with classification "
              "reviewer-absent; only the independent adversarial reviewer closes "
              "(verdict=PASS + independent=true)."),
}

for uid in L.UIDS:
    if uid == "TST-0005":
        continue  # sidecar already carries the NOT-REVIEWED reviewer object
    p = REPO / "command-center" / "receipts" / f"{uid}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(d.get("reviewer"), dict):
        d["reviewer"] = dict(REVIEWER)
        p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
        print(f"{uid}: reviewer -> NOT-REVIEWED")
    else:
        print(f"{uid}: reviewer already object")
