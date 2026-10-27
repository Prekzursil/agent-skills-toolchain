import re
from pathlib import Path
REPO = Path.home() / "p2-g1"
for uid in ["AUD-0068", "AUD-0080", "CNF-0097"]:
    p = REPO / "command-center/p2-wave/probes" / uid / "write_receipts.py"
    print("=" * 20, uid, "=" * 20)
    text = p.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(r"OUT|receipts|state|reviewer|classification|def main|SENT", line):
            print("%4d %s" % (i, line))
