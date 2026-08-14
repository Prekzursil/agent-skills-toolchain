"""Repair the severed O12/O13 rows in command-center/GRIND-STATUS.md.

A blank line between the O11 row and the O13 row severs the last two rows from the markdown
table, so they render as literal pipe text; and they run backwards (O13 before O12).
Idempotent: exits 0 with 'already-repaired' if the shape is already correct.
"""

import sys
from pathlib import Path

P = Path(__file__).resolve().parent / "GRIND-STATUS.md"
txt = P.read_text(encoding="utf-8", newline="")
if "\r\n" in txt:
    sys.exit("FAILED:fixtable file is CRLF; refusing to rewrite and change every line")

lines = txt.split("\n")
i11 = next((i for i, ln in enumerate(lines) if ln.startswith("| O11 |")), None)
i13 = next((i for i, ln in enumerate(lines) if ln.startswith("| O13 |")), None)
i12 = next((i for i, ln in enumerate(lines) if ln.startswith("| O12 |")), None)
if None in (i11, i13, i12):
    sys.exit("FAILED:fixtable could not locate O11/O12/O13 rows")

if i12 == i11 + 1 and i13 == i11 + 2:
    print("SUCCESS:fixtable already-repaired")
    sys.exit(0)

# expected broken shape: O11, blank, O13, O12
if not (lines[i11 + 1].strip() == "" and i13 == i11 + 2 and i12 == i11 + 3):
    sys.exit(
        f"FAILED:fixtable unexpected shape O11={i11} O13={i13} O12={i12} "
        f"blank={lines[i11 + 1]!r}"
    )

row13, row12 = lines[i13], lines[i12]
new = lines[: i11 + 1] + [row12, row13] + lines[i12 + 1 :]
P.write_text("\n".join(new), encoding="utf-8", newline="")

# read back and prove the repair
back = P.read_text(encoding="utf-8", newline="").split("\n")
j11 = next(i for i, ln in enumerate(back) if ln.startswith("| O11 |"))
ok = back[j11 + 1].startswith("| O12 |") and back[j11 + 2].startswith("| O13 |")
print(
    f"SUCCESS:fixtable contiguous={ok} rows_now={back[j11]:.6}|{back[j11 + 1]:.6}|{back[j11 + 2]:.6}"
    if ok
    else "FAILED:fixtable readback disagrees"
)
sys.exit(0 if ok else 1)
