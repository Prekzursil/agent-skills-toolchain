#!/usr/bin/env python3
"""Probe 1: 100-repeat + shuffle invariance + PYTHONHASHSEED (IMP-0083)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace import scenarios as S  # noqa: E402
from marketplace.resolver import (  # noqa: E402
    assert_solution_satisfies,
    repeat_digests,
    resolve,
    solution_digest,
)

ART = REPO / "command-center/receipts/IMP-0083.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0083-probe1 {msg}")
    return 1


def main() -> int:
    index = S.sat_diamond_index()
    request = S.sat_diamond_request()
    result = resolve(index, request)
    print(f"status={result.status} solution={result.solution}")
    if result.status != "SAT":
        return fail("diamond was not SAT")
    if result.solution != S.expected_diamond_solution():
        return fail(f"unexpected solution {result.solution}")
    try:
        assert_solution_satisfies(index, result)
    except AssertionError as exc:
        return fail(f"independent checker: {exc}")
    base = solution_digest(result)
    repeats = set(repeat_digests(index, request, n=100))
    print(f"repeat_distinct={len(repeats)} digest={base}")
    if repeats != {base}:
        return fail(f"100 repeats produced {len(repeats)} digests")

    shuffle_digests = set()
    for seed in range(20):
        shuffled = S.shuffle_index(index, seed)
        got = resolve(shuffled, request)
        if got.status != "SAT" or got.solution != result.solution:
            return fail(f"shuffle seed={seed} drifted {got.to_dict()}")
        assert_solution_satisfies(shuffled, got)
        shuffle_digests.add(solution_digest(got))
    print(f"shuffle_distinct={len(shuffle_digests)}")
    if shuffle_digests != {base}:
        return fail(f"shuffle produced {len(shuffle_digests)} digests")

    script = (
        "import sys; sys.path.insert(0, %r); "
        "from marketplace.resolver import resolve, solution_digest; "
        "from marketplace import scenarios as S; "
        "print(solution_digest(resolve(S.sat_diamond_index(), S.sat_diamond_request())))"
        % str(TOOLS)
    )
    seed_digests = []
    for seed in ("0", "1", "random"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if p.returncode != 0:
            return fail(f"PYTHONHASHSEED={seed} rc={p.returncode} {p.stderr[-400:]}")
        seed_digests.append(p.stdout.strip().splitlines()[-1])
    print(f"hashseed_digests={seed_digests}")
    if len(set(seed_digests)) != 1 or seed_digests[0] != base:
        return fail(f"PYTHONHASHSEED changed digest {seed_digests} vs {base}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0083" not in text:
        return fail("sentinel absent")
    print("SUCCESS:IMP-0083-probe1 repeat-shuffle-hashseed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
