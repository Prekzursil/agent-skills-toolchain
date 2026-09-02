"""Repair the three tracked .json files that do not parse. One-shot, idempotent, verifiable.

Two distinct causes, two distinct repairs, and neither changes a single datum:

  1. TERMINAL MARKER AFTER THE CLOSING BRACE -- PROOF-e2e.json and
     _wave1audit_mutation_selfcheck.json. A probe prints its result document and its
     AGENTS.md-section-4 `SUCCESS:`/`FAILED:` marker to the SAME stdout
     (`platform/marketplace/probe_e2e_marketplace.py:330-331`), and someone redirected stdout into a
     .json file. The marker is not noise -- it is the terminal-state contract -- so it is FOLDED IN
     as a `terminal_marker` field rather than deleted. The document keeps its verdict and starts
     parsing.

  2. UTF-8 BOM -- hooks/worktree-debug.json. Three bytes, EF BB BF. Its only consumer
     (`agent-self/harness/modules.py:3124`) never parses it -- it checks existence and reports the
     file as an "orphaned worktree marker", i.e. the harness already classifies it as debris. So
     the BOM harms nothing today; stripping it costs 3 bytes and removes a permanent false positive
     from any JSON gate. Whether the file should exist at all is an owner call, not mine.

WHAT THIS DELIBERATELY DOES NOT DO: touch either git-crypt `accounts.json`. They fail to decode
because they are ciphertext, they are excluded by the gate on two independent signals, and writing
to one would destroy encrypted credential material.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

MARKER_FILES = (
    "platform/marketplace/PROOF-e2e.json",
    "command-center/_wave1audit_mutation_selfcheck.json",
)
BOM_FILES = ("hooks/worktree-debug.json",)
BOM = b"\xef\xbb\xbf"


def fix_marker(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    end = raw.rfind("}")
    if end == -1:
        return "no closing brace -- SKIPPED"
    body, tail = raw[: end + 1], raw[end + 1 :].strip()
    if not tail:
        return "no trailing marker -- already clean"
    doc = json.loads(
        body
    )  # raises if the object half is also malformed: fail loudly, not silently
    if "terminal_marker" in doc:
        return "terminal_marker already present -- SKIPPED"
    doc["terminal_marker"] = tail
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    return f"folded {tail!r} into terminal_marker"


def fix_bom(path: Path) -> str:
    raw = path.read_bytes()
    if not raw.startswith(BOM):
        return "no BOM -- already clean"
    path.write_bytes(raw[len(BOM) :])
    return f"stripped {len(BOM)}-byte UTF-8 BOM"


def main() -> int:
    changed = []
    for rel in MARKER_FILES:
        p = REPO / rel
        if not p.exists():
            print(f"  ABSENT {rel}")
            continue
        note = fix_marker(p)
        print(f"  {rel}\n      {note}")
        changed.append(rel)
    for rel in BOM_FILES:
        p = REPO / rel
        if not p.exists():
            print(f"  ABSENT {rel}")
            continue
        note = fix_bom(p)
        print(f"  {rel}\n      {note}")
        changed.append(rel)

    # Post-condition: every file touched must now parse, and its data must be intact.
    for rel in changed:
        try:
            json.loads((REPO / rel).read_text(encoding="utf-8"))
        except ValueError as exc:
            print(f"FAILED:fix-json {rel} STILL does not parse: {exc}")
            return 1
    print(f"\nSUCCESS:fix-json {len(changed)} file(s) repaired and re-parsed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
