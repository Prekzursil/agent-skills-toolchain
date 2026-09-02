"""ADV-0041 verifier probe, method=file-read (NOT a shell command).

WHY THIS EXISTS
    The repo's own completion predicate (platform/lib/completion_predicate.py,
    ``_c6_evidence_anchors``) requires the SOURCE and the FIRST VERIFIER probe of a
    CONFIRMED evidence item to declare *different* ``method`` values, because "two
    probes of the same mechanism class are not independent". Evidence item 5 of
    ADV-0041 declared source=``command`` (a bespoke Python token scanner invoked
    through a shell) and verifier=``command`` (``git ls-files`` piped into ``grep``).
    Both labels were accurate, so relabelling one would have been gate-gaming.

    This probe adds a genuinely different mechanism: no shell, no subprocess, no
    regex engine over a directory walk. It opens each declared file with Python's
    own file API and counts literal token occurrences with ``bytes.count``. That is
    the ``file-read`` mechanism class, and it can disagree with the other two.

DETECTOR CONTROL
    A zero from an unproven detector is not evidence (rules/common/single-signal-
    verification.md). This probe therefore also counts a token that MUST be absent
    (``ZZ-NEUTRAL-ABSENT-TOKEN``) and a token that MUST be present, and prints both.
    If the absent-token count is not 0, or the present-token count is 0, the counter
    itself is broken and the run exits non-zero.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The files evidence[5] names in its anchor.
DECLARED = [
    "release/package.json",
    "release/platforms/windows/codex-config.toml",
    "release/platforms/windows/claude-config.json",
    "release/platforms/windows/gemini-settings.json",
    "release/platforms/windows/codex-AGENTS.md",
    "release/platforms/windows/CONSULTATION_WORKFLOW.md",
]

TOKEN = b"Prekzursil"
TOKEN_LOWER = b"prekzursil"
ABSENT = b"ZZ-NEUTRAL-ABSENT-TOKEN"


def main() -> int:
    total = 0
    total_cap = 0
    files_with = 0
    absent_total = 0
    print("method=file-read  (Python open()/bytes.count; no shell, no subprocess, no regex)")
    print(f"repo_root={REPO}")
    print("-" * 72)
    for rel in DECLARED:
        p = REPO / rel
        if not p.is_file():
            print(f"{rel:<52} MISSING")
            continue
        data = p.read_bytes()
        cap = data.count(TOKEN)
        low = data.count(TOKEN_LOWER)
        n = cap + low
        a = data.count(ABSENT)
        total += n
        total_cap += cap
        absent_total += a
        if n:
            files_with += 1
        print(
            f"{rel:<52} bytes={len(data):<7} cap={cap:<4} lower={low:<4} "
            f"sum={n:<4} absent_ctrl={a}"
        )
    print("-" * 72)
    print(f"TOTAL capitalised 'Prekzursil'                         : {total_cap}")
    print(f"TOTAL both cases                                      : {total}")
    print(f"files with >=1 occurrence                             : {files_with}")
    print(f"DETECTOR CONTROL absent-token total (must be 0)       : {absent_total}")
    ok = absent_total == 0 and total > 0
    print(f"DETECTOR CONTROL verdict                              : {'OK' if ok else 'BROKEN'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
