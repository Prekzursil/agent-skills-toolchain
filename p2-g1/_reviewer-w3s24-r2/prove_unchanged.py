import hashlib
import json
from pathlib import Path

recs = ["TST-0206", "TST-0215", "TST-0219", "TST-0221",
        "TST-0223", "TST-0227", "TST-0230", "TST-0233"]
batt = json.loads(Path(r"C:/Users/Prekzursil/p2-g1/_reviewer-w3s24-r2/battery_results.json").read_text(encoding="utf-8"))
for uid in recs:
    p = Path(rf"C:/Users/Prekzursil/p2-g1/command-center/receipts/{uid}.json")
    now = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    print(uid, "| unchanged since battery:", now == batt[uid]["receipt_sha256_LF"])
