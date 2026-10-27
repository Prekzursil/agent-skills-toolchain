import json
from pathlib import Path
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
doc = json.loads((REPO/"command-center/receipts/IMP-0470.json").read_text(encoding="utf-8"))
print(json.dumps(doc.get("reviewer"), indent=1))
print("---failure:", json.dumps(doc.get("failure")))
print("---state:", doc.get("state"))
