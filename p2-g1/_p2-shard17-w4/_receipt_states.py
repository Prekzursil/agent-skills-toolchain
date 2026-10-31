"""Check receipt state/reviewer fields for all shard17-w4 units."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
mine = ["TST-0032", "TST-0057", "TST-0060", "TST-0066", "TST-0067", "TST-0068",
        "TST-0070", "TST-0081", "TST-0085", "TST-0088", "TST-0090", "TST-0091"]

for uid in mine:
    p = REPO / "command-center" / "receipts" / f"{uid}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    rev = d.get("reviewer") or {}
    fail = d.get("failure") or {}
    print("%s state=%r verdict=%r independent=%r fail.class=%r notes=%r" % (
        uid, d.get("state"),
        rev.get("verdict") if isinstance(rev, dict) else None,
        rev.get("independent") if isinstance(rev, dict) else None,
        fail.get("classification"),
        (d.get("notes") or "")[:100]))
