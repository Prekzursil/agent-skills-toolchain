"""Append the ``<!--argv-invalid-->`` marker to the lines that QUOTE a broken command.

Round 4 housekeeping, run once, kept because its control is the evidence that it changed only
what it claims to change. Three round-3 review artifacts REPORT the ``--json --md`` defect and
therefore quote it; ``r4_receipt_argv_gate.py`` must be told those are mentions, not receipts.
The marker is an HTML comment: invisible when rendered, and the reviewers' words are untouched.

It marks exactly the lines the GATE flags -- it imports the gate's own extractor and validity
check rather than grepping for a string. A grep would have marked eight lines in one file where
the gate flags three, sprinkling inert markers over prose that merely names the flags.

TWO CONTROLS, both of which fired on the first version of this script and are the reason it is
committed rather than deleted:

1. Content identity. For each file it prints the sha256 of the content with the exact inserted
   token removed, before and after. The first version stripped only ``MARKER`` and not the two
   spaces preceding it, so the digests differed and it reported CONTENT CHANGED -- correctly.
2. Check BEFORE write. That first version wrote the file and compared afterwards, so it had
   already modified a reviewer's artifact by the time its own control objected. This one
   computes both digests in memory and writes only if they match.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from r4_receipt_argv_gate import (  # noqa: E402  (path shim must precede the import)
    MARKER,
    argv_is_valid,
    extract,
    literal_flags,
    parser_of,
)

HERE = Path(__file__).resolve().parent
INSERT = f"  {MARKER}"

TARGETS = (
    "RULE-AUDIT-ADV-R3.md",
    "RULE-AUDIT-VERIFY-R3.md",
)


def digest_without_insert(text: str) -> str:
    """sha256 of the content with the inserted token removed -- markers AND their padding."""
    bare = text.replace(INSERT, "").replace(MARKER, "")
    return hashlib.sha256(bare.encode("utf-8")).hexdigest()[:16]


def invalid_lines(text: str, doc: str) -> set[int]:
    """Line numbers carrying an invocation the gate rejects. Uses the gate, not a grep."""
    scripts = {p.name: p for p in HERE.glob("*.py")}
    bad: set[int] = set()
    for inv in extract(text, doc):
        path = scripts.get(inv.script)
        if path is None:
            continue
        parser = parser_of(path)
        if parser is not None:
            # The gate's own checker, not a re-implementation: it swallows argparse's usage
            # noise. The first version re-implemented it and printed six usage errors into the
            # run log, which reads exactly like the failure it is here to annotate.
            if not argv_is_valid(parser, inv.argv):
                bad.add(inv.lineno)
            continue
        accepted = literal_flags(path)
        if any(
            t.startswith("-") and t.split("=", 1)[0] not in accepted for t in inv.argv
        ):
            bad.add(inv.lineno)
    return bad


def main() -> int:
    changed = 0
    for name in TARGETS:
        path = HERE / name
        if not path.exists():
            print(f"FAILED:r4_mark_mentions {name} is missing")
            return 1
        original = path.read_text(encoding="utf-8", newline="")
        targets = invalid_lines(original, name)
        out: list[str] = []
        hits = 0
        for lineno, line in enumerate(original.splitlines(keepends=True), start=1):
            body = line.rstrip("\r\n")
            ending = line[len(body) :]
            if lineno in targets and MARKER not in body:
                body += INSERT
                hits += 1
            out.append(body + ending)
        updated = "".join(out)
        before, after = digest_without_insert(original), digest_without_insert(updated)
        if before != after:
            print(f"{name}: stripped-sha {before} -> {after}  CONTENT CHANGED")
            print("FAILED:r4_mark_mentions the edit altered content, not just markers")
            return 1
        if hits:
            path.write_text(updated, encoding="utf-8", newline="")
        changed += hits
        print(
            f"{name}: {len(targets)} flagged line(s), {hits} newly marked · "
            f"stripped-sha {before} == {after}  OK"
        )
    print(
        f"SUCCESS:r4_mark_mentions {changed} quotation(s) marked, content sha unchanged"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
