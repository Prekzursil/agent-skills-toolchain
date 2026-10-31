import json
from pathlib import Path
REPO = Path.home() / "p2-g1"
wave = ["ADV-0015", "AUD-0068", "AUD-0080", "BLD-0002", "BLD-0062", "CC-0008",
        "CNF-0097", "CNF-0146", "CNF-0149", "CNF-0158", "IMP-0070", "IMP-0090",
        "IMP-0102", "IMP-0131", "IMP-0221"]
for uid in wave:
    rp = REPO / "command-center" / "receipts" / (uid + ".json")
    if not rp.is_file():
        print(uid, "RECEIPT-ABSENT")
        continue
    try:
        d = json.loads(rp.read_text(encoding="utf-8"))
    except Exception as e:
        print(uid, "UNPARSEABLE", e)
        continue
    rev = d.get("reviewer") or {}
    fail = d.get("failure") or {}
    print(uid, "| state:", d.get("state"),
          "| reviewer:", rev.get("reviewer_id"), rev.get("verdict"), "independent:", rev.get("independent"),
          "| failure:", fail.get("classification"),
          "| unit_id:", d.get("unit_id"), "| sentinel:", repr(d.get("sentinel"))[:60])
