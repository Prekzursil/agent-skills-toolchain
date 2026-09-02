"""Live reproduction of `grep -c pat || echo 0` printing 0 then 0 again."""
from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from invariants import RunOutput, check_invariants
from naive import UNIVERSE, naive_from_grep_c_blob

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "prs.txt"
MISS_PATTERN = "DOES-NOT-OCCUR"
HIT_PATTERN = "PR-"


def _bash(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )


def grep_c_or_echo_zero(pattern: str, path: Path) -> str:
    """The defective idiom: grep -c prints 0 AND exits 1, so echo 0 also fires."""
    cmd = f"grep -c {shlex.quote(pattern)} {shlex.quote(str(path))} || echo 0"
    return _bash(cmd).stdout


def grep_c_stdout_only(pattern: str, path: Path) -> str:
    """Corrected capture: take grep -c's printed integer; do not `|| echo 0`."""
    cmd = f"grep -c {shlex.quote(pattern)} {shlex.quote(str(path))} || true"
    # `|| true` swallows the exit without printing a second zero.
    # grep -c still printed the first 0. stdout is a single 0 line.
    return _bash(cmd).stdout


def universe_size(path: Path = FIXTURE) -> int:
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def planted_bad() -> dict:
    raw = grep_c_or_echo_zero(MISS_PATTERN, FIXTURE)
    run = naive_from_grep_c_blob(raw, universe=universe_size())
    result = check_invariants(run)
    lines = [ln for ln in raw.splitlines() if ln.strip() != ""]
    return {
        "fixture": f"{FIXTURE.as_posix()}:{MISS_PATTERN}:grep -c || echo 0",
        "command": f"grep -c {MISS_PATTERN} fixtures/prs.txt || echo 0",
        "raw_stdout": raw,
        "raw_lines": lines,
        "doubled_zero": lines == ["0", "0"],
        "naive_claims": sorted(run.claims),
        "naive_counts": run.counts,
        "fired": result.ok is False,
        "classification": result.classification,
        "violated_invariants": list(result.violated),
        "published_numbers": result.published_numbers,
        "message": result.message,
        "verbatim": raw if raw else "(empty)",
    }


def known_good() -> dict:
    raw = grep_c_stdout_only(MISS_PATTERN, FIXTURE)
    run = naive_from_grep_c_blob(raw, universe=universe_size())
    result = check_invariants(run)
    return {
        "fixture": f"{FIXTURE.as_posix()}:{MISS_PATTERN}:grep -c || true",
        "command": f"grep -c {MISS_PATTERN} fixtures/prs.txt || true",
        "raw_stdout": raw,
        "naive_claims": sorted(run.claims),
        "naive_counts": run.counts,
        "fired": result.ok is False,
        "classification": result.classification,
        "published_numbers": result.published_numbers,
        "message": result.message,
        "verbatim": raw if raw else "(empty)",
    }


def both_states() -> dict:
    bad = planted_bad()
    good = known_good()
    return {
        "planted_bad": bad,
        "known_good": good,
        "pass": bool(bad["fired"]) and (not bool(good["fired"])),
        "universe": universe_size(),
    }


def structured_run(
    hit: int,
    miss: int,
    universe: int,
    intersection: int,
    claims: set[str] | None = None,
) -> RunOutput:
    return RunOutput(
        counts={
            "hit": hit,
            "miss": miss,
            "universe": universe,
            "intersection": intersection,
        },
        claims=set(claims or set()),
        raw="",
        n_universe=universe,
    )
