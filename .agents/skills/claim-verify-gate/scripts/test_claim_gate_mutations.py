"""Mutation probe: does the suite actually PROTECT claim_gate's behaviour?

Each mutation reverts one load-bearing decision. A suite that stays green under
a mutation is not testing that decision (single-signal-verification.md:44).
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "claim_gate.py"
TEST = HERE / "test_claim_gate.py"

MUTATIONS = [
    (
        "AXES includes command (so a command-only tweak reads as independent)",
        'AXES = ("tool", "engine", "shell", "field")',
        'AXES = ("tool", "engine", "shell", "field", "command")',
    ),
    (
        "tail share 0.15 -> 1.0 (whole doc counts as tail)",
        "_TAIL_SHARE = 0.15",
        "_TAIL_SHARE = 1.0",
    ),
    (
        "tail share 0.15 -> 0.05 (window too narrow to flag a trailing tag)",
        "_TAIL_SHARE = 0.15",
        "_TAIL_SHARE = 0.05",
    ),
    (
        "residual never recognised",
        'residual = verdict == "UNVERIFIED" and not violations',
        "residual = False",
    ),
    (
        "evidence anchor accepts any string",
        '_ANCHOR = re.compile(r"https?://\\S+|\\S+:\\d+")',
        '_ANCHOR = re.compile(r".")',
    ),
    (
        "absolute-wording detector disabled",
        'if _ABSOLUTE.search(text) and not _text(claim, "scope"):',
        'if False and _ABSOLUTE.search(text) and not _text(claim, "scope"):',
    ),
]

source = GATE.read_text(encoding="utf-8")
survivors = []
for label, old, new in MUTATIONS:
    if old not in source:
        print(f"  ERROR   anchor not found: {label}")
        survivors.append(label)
        continue
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "claim_gate.py").write_text(
            source.replace(old, new, 1), encoding="utf-8"
        )
        shutil.copy2(TEST, work / "test_claim_gate.py")
        result = subprocess.run(
            [sys.executable, str(work / "test_claim_gate.py")],
            capture_output=True,
            text=True,
        )
    if result.returncode == 0:
        print(f"  SURVIVED {label}")
        survivors.append(label)
    else:
        print(f"  KILLED   {label}")

print(f"\n{len(MUTATIONS) - len(survivors)}/{len(MUTATIONS)} mutations killed")
sys.exit(1 if survivors else 0)
