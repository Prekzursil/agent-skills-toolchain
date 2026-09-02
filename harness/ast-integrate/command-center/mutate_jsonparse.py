r"""Mutation-test the git-crypt attribute branch: swap NUL-join back to newline-join, expect RED.

Written as a file because the previous attempt did this through `python -c` inside bash and the
escaping silently failed to match -- so nothing was mutated, the test "passed", and that pass meant
nothing. A mutation you cannot prove was applied is not a mutation test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TARGET = REPO / "tools/measure-guard/jsonparse.py"
GOOD = 'input="\\0".join(rels) + "\\0",'
BAD = 'input="\\n".join(rels),'


def run_test() -> int:
    return subprocess.run(
        ["python", "-m", "pytest", "tests/test_jsonparse.py", "-q", "-k", "ATTRIBUTE"],
        cwd=str(REPO / "tools/measure-guard"),
        capture_output=True,
        text=True,
        check=False,
    ).returncode


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")
    if GOOD not in original:
        print(
            f"FAILED:mutate-jsonparse anchor not found; refusing to guess. Looked for: {GOOD!r}"
        )
        return 1

    healthy = run_test()
    print(f"  HEALTHY state: pytest rc={healthy} (want 0)")

    TARGET.write_text(original.replace(GOOD, BAD, 1), encoding="utf-8", newline="")
    try:
        applied = BAD in TARGET.read_text(encoding="utf-8")
        print(f"  mutation applied and CONFIRMED in file: {applied}")
        mutated = run_test()
        print(f"  MUTATED state: pytest rc={mutated} (want non-zero)")
    finally:
        TARGET.write_text(original, encoding="utf-8", newline="")
        restored = GOOD in TARGET.read_text(encoding="utf-8")
        print(f"  restored, fix present again: {restored}")

    if healthy == 0 and mutated != 0:
        print(
            "\nSUCCESS:mutate-jsonparse the test KILLS the mutant -- it protects the behaviour"
        )
        return 0
    print(
        "\nFAILED:mutate-jsonparse the mutant SURVIVED -- the test does not protect this behaviour"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
