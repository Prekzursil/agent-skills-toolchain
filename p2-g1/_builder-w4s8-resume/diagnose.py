import json, sys
from pathlib import Path
import importlib.util
REPO = Path.home() / "p2-g1"
spec = importlib.util.spec_from_file_location("rsg", REPO / "platform/lib/receipt_schema_gate.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["rsg"] = mod
spec.loader.exec_module(mod)
units = ["IMP-0071","IMP-0099","IMP-0104","IMP-0113","IMP-0121","IMP-0155","IMP-0166","IMP-0167","IMP-0189","IMP-0194","IMP-0195","IMP-0198"]
for u in units:
    doc = json.loads((REPO / "command-center/receipts" / f"{u}.json").read_text(encoding="utf-8"))
    errs = mod.validate_receipt(doc)
    print("==", u, f"({len(errs)} errors)")
    for e in errs:
        print("   ", e[:170])
