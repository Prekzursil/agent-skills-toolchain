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
        "    if _URL.search(item):",
        "    if True:",
    ),
    # The pre-fix shape. `\\S+:\\d+` accepted a bare timestamp as the file:line anchor a
    # CONFIRMED verdict must carry; making the path-head check unconditional restores exactly
    # that behaviour, so this mutation is the old bug re-injected on purpose.
    (
        "anchor head need not name a file (the pre-fix `\\S+:\\d+` behaviour)",
        r'    if "/" in head or "\\" in head:',
        "    if True:",
    ),
    # RETIRED, recorded rather than deleted: "extension need not contain a letter (a version
    # reads as a filename)", which mutated `_EXTENSION` from the 0-5/letter/0-5 window to
    # `\.[A-Za-z0-9]+$`. It SURVIVED once the extension allowlist landed, because the allowlist
    # already rejects `2` from `v1.2` for the same reason it rejects `com` — so the letter rule
    # had become a second decision guarding nothing. The honest fix was to remove the redundant
    # decision from claim_gate rather than to write a test pinning it: the only shape on which
    # the two forms differed was `x.entitlements:5`, which the window rejected WRONGLY. Its
    # replacement is the allowlist mutation below, which is killed. A survivor that is chased
    # with a test asserting the wrong behaviour is worse than no mutation at all.
    # The auditor's residual, re-injected. Accepting ANY letter-bearing extension is exactly
    # the state in which `example.com:443` passed as a file:line anchor.
    (
        "any letter-bearing extension is a filename (the host.tld:port hole)",
        "        return match.group(1).lower() in _FILE_EXTENSIONS",
        "        return True",
    ),
    # The other direction: without the structural dotfile branch, `.gitattributes:2` is
    # rejected — a real anchor the allowlist alone cannot rescue.
    (
        "dotfiles are not recognised structurally",
        '    if head.startswith("."):',
        "    if False:",
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
