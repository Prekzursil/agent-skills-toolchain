import json
from pathlib import Path
p = Path(__file__).resolve().parent / "class-envelope.measure.jsonl"
want = {
    "ADV-0029", "ADV-0033", "ADV-0039", "IMP-0261", "RES-0001", "TST-0175",
    "CNF-0001", "ADV-0003", "ADV-0009", "ADV-0031", "ADV-0112", "ADV-0117",
    "TST-0204", "TST-0166", "BLD-0051", "AUD-0087",
}
for ln in p.read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    if rec.get("id") in want:
        print("=" * 60)
        print(rec["id"], rec.get("cls"), rec.get("line"))
        print((rec.get("tail") or "")[-800:])
