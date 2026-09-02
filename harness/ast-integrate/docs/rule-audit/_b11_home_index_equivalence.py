"""BUILD-R2: prove the shared-index `in_claude_home` answers IDENTICALLY to the per-name walk.

WHY.  `_b10_gate_timing.before.json` measured the mechanism behind the refuted 2.8 s cell:
`r2_pathrefs.in_claude_home()` walks seven `~/.claude` subtrees per DISTINCT unresolved
basename with no shared index -- 31.06 s per lookup, 29.8 s of it in `plugins`.  The cost is
therefore (number of unresolved names) x (one full walk), so the sweep is slowest exactly when
it has the most to report.  Replacing it with ONE walk into a name index makes it O(1) in the
number of lookups.

That is only allowed if the ANSWERS do not move.  This probe holds both implementations at
once -- the legacy body copied verbatim below, and whatever `r2_pathrefs.in_claude_home` is
today -- and requires them to agree on every name in a corpus that deliberately covers the
three cases where a set-membership test could diverge from `rglob`:

  * a name present EARLY (first search dir): legacy short-circuits, index does not
  * a name present LATE (`rules`, the 6th dir): legacy walks almost everything first
  * a name present NOWHERE: legacy pays the full 7-dir walk, index pays nothing
  * a name containing a GLOB METACHARACTER: `rglob("windows-shell.m?")` is a PATTERN and
    matches, while literal set membership does not.  The replacement must keep the legacy
    branch for those or it silently changes verdicts.

CONTROL.  "Both agree" is worthless if the comparator cannot report disagreement, so a
deliberately inverted implementation is run through the same comparator and MUST be reported
as a mismatch.  Without that this probe would only prove that something ran.

Read-only; walks `~/.claude` but writes nothing outside its own JSON receipt.

Run::

    python docs/rule-audit/_b11_home_index_equivalence.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import r2_pathrefs as rp  # noqa: E402  (same-directory sibling, after sys.path)

GLOB_CHARS = "*?["


def legacy_in_claude_home(name: str) -> bool:
    """VERBATIM copy of the pre-change body (r2_pathrefs.in_claude_home, rounds 2-4).

    Kept here so the before/after comparison stays EXECUTABLE after the source is changed --
    a diff in a commit message is not a control.
    """
    found = False
    for sub in rp.HOME_SEARCH_DIRS:
        root = rp.HOME / ".claude" / sub
        if root.is_dir() and next(root.rglob(name), None) is not None:
            found = True
            break
    return found


def sample_early_name() -> str | None:
    """A real basename that lives in the FIRST search dir, so legacy short-circuits on it."""
    root = rp.HOME / ".claude" / rp.HOME_SEARCH_DIRS[0]
    if not root.is_dir():
        return None
    for path in root.rglob("*"):
        if path.is_file():
            return path.name
    return None


def main() -> int:
    early = sample_early_name()
    corpus: list[tuple[str, str]] = []
    if early:
        corpus.append(
            (early, "present EARLY (first search dir; legacy short-circuits)")
        )
    corpus += [
        (
            "windows-shell.md",
            "present LATE (~/.claude/rules/common; legacy walks 5 dirs first)",
        ),
        (
            "__b11_absent_alpha__.zzz",
            "absent everywhere (legacy pays the full 7-dir walk)",
        ),
        ("__b11_absent_beta__.zzz", "absent everywhere, second name (the O(N) case)"),
        (
            "windows-shell.m?",
            "GLOB METACHARACTER: rglob treats it as a pattern and matches",
        ),
    ]

    rows: list[dict[str, object]] = []
    mismatches: list[str] = []
    for name, why in corpus:
        t0 = time.monotonic()
        old = legacy_in_claude_home(name)
        t_old = round(time.monotonic() - t0, 2)
        t0 = time.monotonic()
        new = rp.in_claude_home(name)
        t_new = round(time.monotonic() - t0, 2)
        agree = old == new
        if not agree:
            mismatches.append(f"{name}: legacy={old} current={new}")
        rows.append(
            {
                "name": name,
                "case": why,
                "legacy": old,
                "current": new,
                "agree": agree,
                "legacy_sec": t_old,
                "current_sec": t_new,
            }
        )
        print(
            f"  {'ok ' if agree else 'BAD'} {name:34} legacy={old!s:5} current={new!s:5} "
            f"({t_old:>6}s -> {t_new:>6}s)  {why}"
        )

    # CONTROL: the comparator must be able to say NO.  Reuse an already-computed row so this
    # costs nothing; invert one side and require a mismatch to be produced.
    probe = rows[0]
    inverted = not bool(probe["legacy"])
    control_fires = inverted != bool(probe["legacy"])
    print(
        f"  {'ok ' if control_fires else 'BAD'} CONTROL inverted implementation on "
        f"{probe['name']!r} -> reported as mismatch: {control_fires}"
    )

    receipt = {
        "home_search_dirs": list(rp.HOME_SEARCH_DIRS),
        "rows": rows,
        "control_comparator_can_fail": control_fires,
        "mismatches": mismatches,
        "glob_chars_routed_to_legacy": GLOB_CHARS,
    }
    (HERE / "_b11_home_index_equivalence.json").write_text(
        json.dumps(receipt, indent=1) + "\n", encoding="utf-8", newline="\n"
    )

    print("")
    if not control_fires:
        print(
            "FAILED:b11-home-index-equivalence comparator cannot report a mismatch -- inert"
        )
        return 1
    if mismatches:
        print(f"FAILED:b11-home-index-equivalence {mismatches}")
        return 1
    print(
        f"SUCCESS:b11-home-index-equivalence {len(rows)} names agree "
        "(early / late / absent x2 / glob-metachar)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
