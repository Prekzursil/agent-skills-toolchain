"""LANE DOCS round 6 -- EOL census of the files this round edits.

Reading or writing a file without ``newline=""`` re-inserts CRLF and turns a 3-line change
into a whole-file diff. This prints the real byte counts so the edit route can be chosen
before any write, and can be re-run afterwards to prove the counts did not move.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TARGETS = [
    "docs/_LANE-DOCS-BUILD-R5.md",
    "ci/tests/test_command_doc_promises.py",
    "docs/_LANE-DOCS-BUILD-R6.md",
    "docs/_lane_docs_r6_pinned_counts.py",
]


def main() -> int:
    rc = 0
    for rel in TARGETS:
        p = REPO / rel
        if not p.is_file():
            print(f"{rel:45s} ABSENT")
            rc = 1
            continue
        data = p.read_bytes()
        crlf = data.count(b"\r\n")
        lf = data.count(b"\n")
        lone_cr = data.count(b"\r") - crlf
        kind = "CRLF" if crlf and crlf == lf else ("LF" if crlf == 0 else "MIXED")
        print(
            f"{rel:45s} bytes={len(data):7d} CRLF={crlf:5d} LF={lf:5d} "
            f"loneCR={lone_cr:3d} -> {kind}"
        )
        if kind == "MIXED":
            rc = 1
    print("SUCCESS:docs-r6-eol" if rc == 0 else "FAILED:docs-r6-eol mixed-or-absent")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
