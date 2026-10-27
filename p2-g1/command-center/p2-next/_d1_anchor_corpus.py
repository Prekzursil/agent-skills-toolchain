"""Measure the evidence-anchor corpus BEFORE tightening claim_gate's `_ANCHOR`.

The previous round (00d0a311) closed claim_gate's no-source-probe hole and disclosed, but did
NOT fix, a second one: `_ANCHOR = r"https?://\\S+|\\S+:\\d+"` accepts a bare TIMESTAMP
(`2026-08-12T05:15:00`) as the file:line anchor a CONFIRMED verdict is required to carry. Its
stated reason for deferring was "one behaviour change to a shared skill per round, and that one
has no measured false-negative yet".

This probe supplies the missing measurement, in both directions:

  FALSE NEGATIVE  which non-reference tokens the CURRENT rule accepts as an anchor.
  FALSE POSITIVE  which anchors REAL committed claim ledgers carry, and whether a stricter rule
                  would reject any of them. That is the risk the tightening must not realise --
                  rejecting `Makefile:12` to catch a timestamp is a bad trade.

Three candidate rules are compared, because the OBVIOUS strict rule (require a file extension,
the shape rail_count_gate.py:133 already uses) is measurably wrong in the other direction.

Reads COMMITTED BLOBS via `git show`, never the worktree, because siblings are mid-edit.
Decodes as UTF-8 with replacement: a cp1252 decode failure silently DROPPED a ledger on the
first run of this probe, which would have understated the false-positive count.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

CURRENT = re.compile(r"https?://\S+|\S+:\d+")
# The shape rail_count_gate.py:133 already uses for the SAME question.
STRICT_EXT = re.compile(r"([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,6}):(\d+)|https?://\S+")

# ---- the CANDIDATE rule, mirrored exactly from what will ship in claim_gate.py ----
_URL = re.compile(r"https?://\S+")
_FILE_LINE = re.compile(
    r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.][A-Za-z0-9_./\\-]*):(\d+)\b"
)
# A real extension carries at least one LETTER (`.py`, `.md`, `.7z`); `v1.2` does not.
_EXTENSION = re.compile(r"\.[A-Za-z0-9]{0,5}[A-Za-z][A-Za-z0-9]{0,5}$")
_EXTENSIONLESS = frozenset(
    {
        "makefile",
        "dockerfile",
        "license",
        "licence",
        "notice",
        "readme",
        "changelog",
        "codeowners",
        "procfile",
        "gemfile",
        "rakefile",
        "jenkinsfile",
        "vagrantfile",
        "justfile",
    }
)


def _is_path_head(head: str) -> bool:
    if "/" in head or "\\" in head:
        return True
    if _EXTENSION.search(head):
        return True
    return head.lower() in _EXTENSIONLESS


def candidate(item: str) -> bool:
    if _URL.search(item):
        return True
    return any(_is_path_head(m.group(1)) for m in _FILE_LINE.finditer(item))


# Tokens that are NOT references to anything readable, but which a `\S+:\d+` rule accepts.
NON_REFERENCES = [
    "2026-08-12T05:15:00",
    "2026-08-12T05:15",
    "05:15",
    "12:30:45",
    "PT1H:30",
    "ratio 3:1",
    "score 9:2",
    "v1.2:3",
    "measured at 2026-08-12T05:15:00 by the reviewer",
]

# Real anchors that MUST keep passing. Extension-less filenames and Windows drive-letter paths
# are the false-positive risks of an extension-required rule on THIS estate.
REAL_ANCHORS = [
    "tools/mcp/host.py:12",
    "command-center/p2-next/rail_count_gate.py:133",
    ".github/workflows/quality.yml:1026",
    "rules/common/single-signal-verification.md:75",
    "https://arxiv.org/abs/2601.08654",
    "Makefile:12",
    "Dockerfile:5",
    "LICENSE:3",
    "C:\\Users\\Prekzursil\\source\\ast-integrate\\claim_gate.py:113",
    "see receipt_schema_gate.py:515 for the reject",
]


def git_show(rev: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout if proc.returncode == 0 else None


def tracked_json() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "*.json"],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    proc.check_returncode()
    return [line for line in proc.stdout.splitlines() if line.strip()]


def harvest_ledger_evidence() -> tuple[list[tuple[str, str]], int, int]:
    """Every `evidence` string from every COMMITTED claim-ledger-shaped JSON."""
    found: list[tuple[str, str]] = []
    ledgers = 0
    unreadable = 0
    for path in tracked_json():
        blob = git_show("HEAD", path)
        if blob is None:
            unreadable += 1
            continue
        if '"claims"' not in blob:
            continue
        try:
            payload = json.loads(blob)
        except ValueError:
            unreadable += 1
            continue
        claims = payload.get("claims") if isinstance(payload, dict) else None
        if not isinstance(claims, list):
            continue
        shaped = False
        for claim in claims:
            if not isinstance(claim, dict) or "verdict" not in claim:
                continue
            shaped = True
            # `evidence` is a STRING in the estate's real registries
            # (command-center/CLAIM-REGISTRY.json) and a LIST in claim_gate's own fixtures.
            # Iterating the string form yields CHARACTERS -- the first version of this
            # harvester did exactly that and reported "4436 evidence strings, 0 anchored",
            # which is 4436 single characters, none of which can contain `file:line`.
            # Caught by _d2_registry_shape.py, not by reading this code.
            ev = claim.get("evidence")
            items = ev if isinstance(ev, list) else ([ev] if ev is not None else [])
            for item in items:
                if isinstance(item, str):
                    found.append((path, item))
        if shaped:
            ledgers += 1
    return found, ledgers, unreadable


def report() -> int:
    print("== A. FALSE NEGATIVE: non-reference tokens the CURRENT rule accepts ==")
    accepted_cur = accepted_cand = 0
    for token in NON_REFERENCES:
        cur, cand = bool(CURRENT.search(token)), candidate(token)
        accepted_cur += cur
        accepted_cand += cand
        print(
            f"  current={'PASS' if cur else 'fire'}  "
            f"candidate={'PASS' if cand else 'fire'}  {token!r}"
        )
    print(
        f"  -> current accepts {accepted_cur}/{len(NON_REFERENCES)} non-references; "
        f"candidate accepts {accepted_cand}/{len(NON_REFERENCES)}"
    )

    print()
    print("== B. FALSE POSITIVE: real anchors a stricter rule must not reject ==")
    ext_regressions, cand_regressions = [], []
    for token in REAL_ANCHORS:
        cur = bool(CURRENT.search(token))
        ext = bool(STRICT_EXT.search(token))
        cand = candidate(token)
        if cur and not ext:
            ext_regressions.append(token)
        if cur and not cand:
            cand_regressions.append(token)
        print(
            f"  current={'PASS' if cur else 'fire'}  "
            f"ext-required={'PASS' if ext else 'fire'}  "
            f"candidate={'PASS' if cand else 'fire'}  {token!r}"
        )
    print(
        f"  -> ext-required would REJECT {len(ext_regressions)} real anchors: {ext_regressions}"
    )
    print(
        f"  -> CANDIDATE would REJECT {len(cand_regressions)} real anchors: {cand_regressions}"
    )

    print()
    print("== C. The committed corpus: what real ledgers actually carry ==")
    evidence, ledgers, unreadable = harvest_ledger_evidence()
    print(f"  claim-ledger-shaped committed JSON files: {ledgers}")
    print(f"  evidence strings harvested: {len(evidence)}")
    print(f"  files skipped as unreadable/unparseable: {unreadable}")
    anchored_now = [(p, i) for p, i in evidence if CURRENT.search(i)]
    print(f"  strings the CURRENT rule counts as an anchor: {len(anchored_now)}")
    regressions = [(p, i) for p, i in anchored_now if not candidate(i)]
    print(f"  of those, strings the CANDIDATE would newly reject: {len(regressions)}")
    for path, item in regressions[:25]:
        print(f"    {path}: {item[:120]!r}")
    if not anchored_now:
        print(
            "  NOTE: zero anchored strings -- section C measures NOTHING and must not be"
        )
        print(
            "        cited as evidence the tightening is safe. Section B carries the verdict."
        )
    return 0


if __name__ == "__main__":
    sys.exit(report())
