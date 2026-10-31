#!/usr/bin/env python3
"""C1 pre-state probe: is tools/wf-timeout named ANYWHERE in .github/** or ci/**?

Detector control: the same scan also counts a needle that IS present in those trees
(``pytest``) and one that must be absent (``ZZ_CONTROL_MUST_BE_ZERO_ZZ``).  If the
present-control reads 0 the scanner is broken and the absence verdict means nothing.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TREES = [ROOT / ".github", ROOT / "ci"]

TARGETS = ["wf-timeout", "wf_gate", "h6_extract", "h6_harness", "test_h6_timeout"]
CONTROL_PRESENT = "pytest"
CONTROL_ABSENT = "ZZ_CONTROL_MUST_BE_ZERO_ZZ"


def scan() -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {
        n: [] for n in TARGETS + [CONTROL_PRESENT, CONTROL_ABSENT]
    }
    files = 0
    for tree in TREES:
        for path in sorted(tree.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            files += 1
            rel = path.relative_to(ROOT).as_posix()
            for needle in hits:
                if needle in text:
                    hits[needle].append(rel)
    print(f"files scanned: {files}")
    return hits


def main() -> int:
    hits = scan()
    ok_present = len(hits[CONTROL_PRESENT]) > 0
    ok_absent = len(hits[CONTROL_ABSENT]) == 0
    print(
        f"CONTROL present-needle {CONTROL_PRESENT!r}: {len(hits[CONTROL_PRESENT])} file(s)"
    )
    print(
        f"CONTROL absent-needle:                    {len(hits[CONTROL_ABSENT])} file(s)"
    )
    if not (ok_present and ok_absent):
        print("FAILED:c1-probe detector control did not hold; absence verdict is void")
        return 1
    total = 0
    for needle in TARGETS:
        found = hits[needle]
        total += len(found)
        print(f"  {needle:<16} -> {len(found)} file(s) {found}")
    print(f"SUCCESS:c1-probe detector_control_ok=True wf_timeout_refs_in_ci={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
