"""Declared minimum test counts per suite: a run below its floor FAILS regardless of exit code.

TST-0350's target, quoted: "a run that collects zero tests exits zero and reports green, and a
benchmark over an empty input set returns a clean, meaningless result - both measured on this
estate. Add the floor: every registered suite declares a minimum expected test count, and a run
below it FAILS regardless of exit code. Same rule for any measurement over a collection: an empty
input is an error, never a pass."

Both halves of that were measured on this repo tonight, which is why this exists as a tested module
rather than a shell one-liner:

  * A fresh `git clone` of main could not COLLECT `platform/` at all - 31 collection errors - while
    the working tree reported 3,910 passed. Nine files that tracked code imports had never been
    committed.
  * The first version of the CI guard for that was an inline `[ "$collected" -lt 3900 ]` in a YAML
    `run:` block. Untested shell inside a workflow file is exactly the shape that produces a gate
    nobody notices has stopped working.

WHY A FLOOR AND NOT JUST "> 0": zero is the easy case. The dangerous case is a partial collapse - an
import error in one package silently removing a few hundred tests while pytest still exits 0 on the
rest. A floor catches that; a non-zero check does not.

The floors here are LOWER than the observed counts on purpose. A floor set to the exact current
count becomes a nuisance gate that fails on every legitimately added test, and a nuisance gate gets
disabled. The margin is stated per suite.

`require_nonempty` EXISTS for the non-pytest half of TST-0350 - a census, a benchmark or a diff over
an empty input set must be an error, never a clean pass - but it currently has ZERO production
callers, so the CAPABILITY is here while the RULE is generalised nowhere. Stated in the present tense
because that is the shipped state; the receipt at command-center/receipts/TST-0350.json records the
same scoping and names the settling experiment. Deliberately NOT satisfied by adding a token call
site, which would launder the sentence instead of doing the work.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: Collected-count pattern from `pytest --collect-only -q`, whose last line is "N tests collected"
#: (or "N test collected" for exactly one).
_COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected")


@dataclass(frozen=True)
class Suite:
    """A registered suite and the floor below which a run is a failure."""

    name: str
    path: str
    minimum: int
    #: Observed count when the floor was set, so the margin is auditable rather than arbitrary.
    observed_when_set: int
    note: str
    #: Per-package floors, checked IN ADDITION to the whole-suite total.
    #:
    #: THE BYPASS THIS CLOSES, found by independent review and measured, not argued: `platform`
    #: holds 3,946 tests with a floor of 3,900, i.e. 46 of slack. `platform/corpus` holds 45.
    #:
    #:     pytest platform --ignore=platform/corpus --collect-only -q  ->  3901 collected
    #:     check_suite: observed=3901  floor=3900  ->  PASS
    #:
    #: An ENTIRE PACKAGE could stop collecting and the gate reported SUCCESS, by a margin of one
    #: test - precisely the case the module docstring above says the floor exists to catch. A
    #: single whole-suite total cannot see it, because the slack needed to avoid being a nuisance
    #: gate is necessarily larger than the smallest package.
    per_package: tuple[tuple[str, int], ...] = ()


#: Every suite that a gate runs. A suite absent from here has NO declared floor, which TST-0350
#: calls "itself a finding" - `unregistered()` reports those rather than passing them silently.
SUITES: tuple[Suite, ...] = (
    Suite(
        name="platform",
        path="platform",
        minimum=3900,
        observed_when_set=3946,
        note=(
            "3,946 collected on a fresh clone of 15cb70e3 (untracked=0), independently confirmed at "
            "3,946 by a GitHub runner (CI run 31410194562) - three platforms, so the reference "
            "count is not machine-specific. Floor 3900 leaves 46 of headroom for growth; the "
            "per-package floors below are what actually catch a package disappearing, since 46 of "
            "slack is wider than the smallest package."
        ),
        per_package=(
            # Measured by bucketing all 3,946 collected node ids by package.
            ("platform/lib", 3000),
            ("platform/plugin", 240),
            ("platform/coordination", 220),
            ("platform/marketplace", 155),
            ("platform/routing", 115),
            # 45 observed. Floor 40 - this is the package the whole-suite total could not protect.
            ("platform/corpus", 40),
        ),
    ),
    Suite(
        name="command-center",
        path="tools/command-center/tests",
        minimum=55,
        observed_when_set=61,
        note="61 collected; floor 55 tolerates removing one test module, not a collapse.",
    ),
    Suite(
        name="casualty",
        path="command-center/casualty/tests",
        minimum=28,
        observed_when_set=32,
        note=(
            "32 collected. The suite is the TESTED disposition for the casualty lane's "
            "integration guard: it is what stands in for census_v2 in CI (census_v2 reads "
            "command-center/adversarial/, which a live sibling wave writes, so pinning its "
            "control pairs would make an unrelated sibling commit a red build). Floor 25 "
            "tolerates dropping a couple of cases, not the both-states half of the file - "
            "every green-state assertion there is paired with a mutation that must go red, so "
            "a collapse to the good state alone would leave the probes untested and is exactly "
            "what this floor exists to catch."
        ),
    ),
)


def suite_by_name(name: str) -> Suite | None:
    return next((s for s in SUITES if s.name == name), None)


def collect_count(path: str, *, cwd: Path | None = None) -> tuple[int, str]:
    """-> (collected, raw tail). A collection ERROR returns 0, which the floor then rejects.

    `--collect-only` is used rather than a full run because the question is how many tests EXIST,
    and a collection error must be indistinguishable from an empty walk as far as the floor is
    concerned: both mean "the suite you think you are running is not there".
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            path,
            "-q",
            "-p",
            "no:cacheprovider",
            "--collect-only",
        ],
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    matches = _COLLECTED_RE.findall(out)
    count = int(matches[-1]) if matches else 0
    tail = "\n".join(out.strip().splitlines()[-3:])
    return count, tail


def check_suite(suite: Suite, *, cwd: Path | None = None) -> tuple[bool, int, str]:
    observed, tail = collect_count(suite.path, cwd=cwd)
    if observed <= 0:
        return (
            False,
            observed,
            f"collected NOTHING (floor {suite.minimum}); tail: {tail}",
        )
    if observed < suite.minimum:
        return (
            False,
            observed,
            f"collected {observed}, below the declared floor {suite.minimum} - a package is "
            f"probably failing to import; tail: {tail}",
        )

    # Per-package floors. The whole-suite total above cannot catch a small package vanishing, so
    # each declared package is checked on its own; the first breach fails the suite and NAMES the
    # package, which the aggregate total never could.
    for pkg, floor in suite.per_package:
        pkg_observed, pkg_tail = collect_count(pkg, cwd=cwd)
        if pkg_observed < floor:
            return (
                False,
                observed,
                f"whole-suite total {observed} clears {suite.minimum}, but package {pkg} collected "
                f"{pkg_observed}, below its floor {floor} - a package can disappear inside the "
                f"aggregate slack; tail: {pkg_tail}",
            )

    extra = f" (+{len(suite.per_package)} package floors)" if suite.per_package else ""
    return True, observed, f"collected {observed} >= floor {suite.minimum}{extra}"


def require_nonempty(count: int, label: str, minimum: int = 1) -> None:
    """Fail closed on an empty or below-floor measurement. Raises ValueError.

    The non-pytest half of TST-0350. A census over zero files, a benchmark over an empty input set
    and a diff over no paths all return a clean, meaningless result otherwise - measured on this
    estate, where two benchmarks reported green over EMPTY inputs.
    """
    if count < minimum:
        raise ValueError(
            f"{label}: {count} item(s) is below the required minimum {minimum}. An empty or "
            "short input set is an ERROR, never a pass - a measurement over nothing cannot "
            "support a verdict."
        )


def unregistered(paths: list[str]) -> list[str]:
    """Paths with no declared floor. TST-0350: 'a suite with no declared minimum is a finding'."""
    known = {s.path for s in SUITES}
    return [p for p in paths if p not in known]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", help="registered suite name; omit for --all")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)

    if args.list:
        for s in SUITES:
            print(
                f"  {s.name:16s} path={s.path:26s} floor={s.minimum:5d} (observed {s.observed_when_set})"
            )
        return 0

    targets: list[Suite]
    if args.all:
        targets = list(SUITES)
    elif args.suite:
        found = suite_by_name(args.suite)
        if found is None:
            names = ", ".join(s.name for s in SUITES)
            print(
                f"FAILED:suite-floor unknown suite {args.suite!r}; registered: {names}"
            )
            return 1
        targets = [found]
    else:
        print("FAILED:suite-floor pass --suite <name>, --all or --list")
        return 1

    if not targets:  # fail closed: an empty target list must never read as success
        print("FAILED:suite-floor no suites selected")
        return 1

    failures = 0
    for suite in targets:
        ok, observed, reason = check_suite(suite)
        marker = "OK  " if ok else "FAIL"
        print(f"  {marker} {suite.name}: {reason}")
        if not ok:
            failures += 1
    if failures:
        print(f"FAILED:suite-floor {failures} suite(s) below floor")
        return 1
    print(f"SUCCESS:suite-floor {len(targets)} suite(s) at or above floor")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
