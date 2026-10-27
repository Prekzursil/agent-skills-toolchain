"""Summarize closure records in SUBAGENT-RETURN.json for shard17-w4 units."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
mine = ["TST-0032", "TST-0057", "TST-0060", "TST-0066", "TST-0067", "TST-0068",
        "TST-0070", "TST-0081", "TST-0085", "TST-0088", "TST-0090", "TST-0091"]

for uid in mine:
    p = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    closure = (d.get("builder_closure") or "")[:110]
    reviewer = d.get("reviewer") or {}
    print("%s status=%r rev(verdict=%s, independent=%s, id=%s)" % (
        uid, d.get("status"),
        reviewer.get("verdict") if isinstance(reviewer, dict) else None,
        reviewer.get("independent") if isinstance(reviewer, dict) else None,
        (reviewer.get("id") or reviewer.get("review_id")) if isinstance(reviewer, dict) else None))
    print("   closure: %s" % closure)
