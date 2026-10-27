"""Both-states control for the round-2 increment (tests/test_registry_commit_truth.py).

A green suite is not evidence that a check works; it is evidence that nothing broke it
TODAY. So each guard in the new module is reverted in turn and the suite must go RED.
A mutation the suite leaves green is a hole, not a pass.

ISOLATION: the real module is never edited. Each mutation is written to a SIBLING file in
the same tests/ directory (so ``REPO = parents[3]`` still resolves to the real repo and the
real-repo controls still exercise the real HEAD), pytest runs ONLY that file, and the
sibling is deleted in a finally. The shared working tree that other lanes are using is
therefore untouched even if this script is killed mid-run -- the worst case is one orphan
``tests/test_zz_mutation_probe.py``, which the final sweep below also removes.

The last case is an INVERTED control: a semantically neutral edit that MUST survive. Without
it, a harness that reported KILLED unconditionally would look perfect.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "tests" / "test_registry_commit_truth.py"
PROBE = HERE / "tests" / "test_zz_mutation_probe.py"

#: (label, old, new, must_die) -- must_die False marks the inverted control.
MUTATIONS: list[tuple[str, str, str, bool]] = [
    (
        "mirror_divergence always reports 'identical'",
        "    bodies = {rel: committed_blob(repo, rel, rev) for rel in rels}",
        "    bodies = {rel: committed_blob(repo, rel, rev) for rel in rels}\n    return None",
        True,
    ),
    (
        "line-ending drift is misreported as content drift",
        '        return ("line-endings", f"identical after LF-normalisation ({sizes})")',
        '        return ("content", f"identical after LF-normalisation ({sizes})")',
        True,
    ),
    (
        "untracked_entries never reports anything",
        "    missing: dict[str, str] = {}",
        "    missing: dict[str, str] = {}\n    return missing",
        True,
    ),
    (
        "an empty tree listing is accepted instead of failing closed",
        "    if not names:",
        "    if False:",
        True,
    ),
    (
        "an absent git silently falls back to a bare 'git'",
        "    if exe is None:",
        "    if exe is None and False:",
        True,
    ),
    (
        "an unreadable revision returns empty bytes instead of raising",
        '    if proc.returncode != 0:\n        raise GitProbeError(\n            f"{rel!r} is not readable',
        '    if proc.returncode != 0:\n        return b""\n    if False:\n        raise GitProbeError(\n            f"{rel!r} is not readable',
        True,
    ),
    (
        "the two-path precondition is dropped",
        "    if len(rels) < 2:",
        "    if False:",
        True,
    ),
    (
        "NO-OP: reword a docstring (inverted control, must SURVIVE)",
        "The instrument could not run. Never downgraded to a skip.",
        "The instrument could not run. Not ever downgraded to a skip.",
        False,
    ),
]


def run_probe() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(PROBE), "-q", "-p", "no:cacheprovider"],
        cwd=str(HERE),
        capture_output=True,
        check=False,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def main() -> int:
    original = SOURCE.read_text(encoding="utf-8")

    baseline_ok = False
    try:
        PROBE.write_text(original, encoding="utf-8")
        code, out = run_probe()
        baseline_ok = code == 0
        print(
            f"[baseline] unmutated copy exit={code} :: {out.strip().splitlines()[-1]}"
        )
    finally:
        PROBE.unlink(missing_ok=True)
    if not baseline_ok:
        print("FAILED:r2-mutation-control the UNMUTATED copy is already red")
        return 1

    killed = 0
    survived_expected = 0
    problems: list[str] = []
    for label, old, new, must_die in MUTATIONS:
        if old not in original:
            problems.append(f"ANCHOR MISS: {label}")
            print(f"  ANCHOR MISS  {label}")
            continue
        mutated = original.replace(old, new, 1)
        try:
            PROBE.write_text(mutated, encoding="utf-8")
            code, out = run_probe()
        finally:
            PROBE.unlink(missing_ok=True)
        tail = out.strip().splitlines()[-1] if out.strip() else "<no output>"
        if must_die:
            if code != 0:
                killed += 1
                print(f"  KILLED       {label} :: {tail}")
            else:
                problems.append(f"SURVIVED: {label}")
                print(f"  SURVIVED     {label} :: {tail}")
        else:
            if code == 0:
                survived_expected += 1
                print(f"  SURVIVED(ok) {label} :: {tail}")
            else:
                problems.append(f"NO-OP KILLED (harness over-fires): {label}")
                print(f"  NO-OP KILLED {label} :: {tail}")

    PROBE.unlink(missing_ok=True)
    assert SOURCE.read_text(encoding="utf-8") == original, (
        "the source module changed during the run"
    )
    print(f"restore verified: {SOURCE.name} is byte-identical to its pre-run text")
    print(f"probe file removed: {not PROBE.exists()}")

    total_die = sum(1 for *_x, must in MUTATIONS if must)
    if problems:
        print(f"FAILED:r2-mutation-control {len(problems)} problem(s): {problems}")
        return 1
    print(
        f"SUCCESS:r2-mutation-control {killed}/{total_die} killed, "
        f"{survived_expected}/1 no-op survived"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
