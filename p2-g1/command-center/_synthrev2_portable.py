"""Make the synthesis-review probes portable before they are committed.

A Windows absolute path frozen into a git blob is one of the five local-green/CI-red mechanisms
this repo has already burned (GRIND-STATUS CL6). These probes hardcoded
`C:/Users/Prekzursil/source/ast-integrate`; rewrite each to derive the repo root from __file__.

Idempotent. Prints a per-file result and a terminal marker.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BAD = "C:/Users/Prekzursil/source/ast-integrate"
NEW = "REPO = Path(__file__).resolve().parent.parent"

TARGETS = [
    "_synthrev2_checks.py",
    "_synthrev2_gates.py",
    "_synthrev2_claims.py",
    "_synthrev2_docs.py",
    "_synthrev2_fixtable.py",
]

failed = []
for name in TARGETS:
    p = HERE / name
    if not p.exists():
        failed.append(f"{name}: MISSING")
        continue
    txt = p.read_text(encoding="utf-8", newline="")
    if "\r\n" in txt:
        failed.append(f"{name}: CRLF, refusing to rewrite")
        continue
    before = txt.count(BAD)
    # the module-level constant
    txt = re.sub(r'^REPO = Path\("' + re.escape(BAD) + r'"\)$', NEW, txt, flags=re.M)
    # the fixtable script targets a file under the repo, not the repo root
    txt = txt.replace(
        'P = Path("' + BAD + '/command-center/GRIND-STATUS.md")',
        'P = Path(__file__).resolve().parent / "GRIND-STATUS.md"',
    )
    after = txt.count(BAD)
    p.write_text(txt, encoding="utf-8", newline="")
    print(f"  {name}: absolute-path hits {before} -> {after}")
    if after:
        failed.append(f"{name}: {after} hardcoded path(s) remain")

if failed:
    print("FAILED:portable " + "; ".join(failed))
    sys.exit(1)
print("SUCCESS:portable no hardcoded estate path remains in any review probe")
