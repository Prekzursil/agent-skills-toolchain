#!/usr/bin/env python3
"""Probe 2: unpin-sampling control + bash sha256sum reviewer rerun.

Mechanically independent of probe 1:
  * uniqueness is counted by sha256sum | sort -u | wc -l in bash (or sh)
  * the load-bearing assertion is variance INCREASE after unpinning sampling
  * token_sum is a different data field from probe 1's unique hashlib count
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0094.json"
HARNESS = HERE / "harness.py"
N = 7
SENTINEL = (
    "SUCCESS:RES-0094 in the receipt AND an N>=5 repeated-run variance figure "
    "plus an unpin-and-increase control"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0094-probe2 {msg}")
    return 1


def pick_shell() -> str:
    for name in ("bash", "sh"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("neither bash nor sh found")


def unique_via_sha256sum(mode: str, n: int, shell: str) -> int:
    script = r"""
set -eu
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 TZ=UTC
N="$1"
MODE="$2"
HARNESS="$3"
i=1
while [ "$i" -le "$N" ]; do
  python3 -B "$HARNESS" run --mode "$MODE" --index "$i" > "$TMP/out_$i.json"
  i=$((i + 1))
done
sha256sum "$TMP"/out_*.json | awk '{print $1}' | sort -u | wc -l
"""
    p = subprocess.run(
        [shell, "-s", str(n), mode, str(HARNESS)],
        input=script,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stdout or "") + (p.stderr or ""))
    return int(p.stdout.strip().split()[0])


def token_sums_via_shell(mode: str, n: int, shell: str) -> list[int]:
    """Parse token_sum with a shell pipeline (grep/tr), not hashlib uniqueness."""
    script = r"""
set -eu
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 TZ=UTC
N="$1"
MODE="$2"
HARNESS="$3"
i=1
while [ "$i" -le "$N" ]; do
  python3 -B "$HARNESS" run --mode "$MODE" --index "$i" \
    | tr ',' '\n' | grep '"token_sum":' | tr -dc '0-9\n'
  i=$((i + 1))
done
"""
    p = subprocess.run(
        [shell, "-s", str(n), mode, str(HARNESS)],
        input=script,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stdout or "") + (p.stderr or ""))
    lines = [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
    if len(lines) != n:
        raise RuntimeError(f"expected {n} token_sum lines got {lines!r}")
    return [int(x) for x in lines]


def sample_variance(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean = sum(xs) / n
    return sum((x - mean) ** 2 for x in xs) / (n - 1)


def main() -> int:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    raw = ART.read_text(encoding="utf-8")
    if SENTINEL not in raw:
        return fail("sentinel-absent")
    doc = json.loads(raw)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    shell = pick_shell()
    pinned_u = unique_via_sha256sum("pinned", N, shell)
    unpin_u = unique_via_sha256sum("unpin-sampling", N, shell)
    pinned_sums = token_sums_via_shell("pinned", N, shell)
    unpin_sums = token_sums_via_shell("unpin-sampling", N, shell)
    pinned_var = sample_variance([float(x) for x in pinned_sums])
    unpin_var = sample_variance([float(x) for x in unpin_sums])

    if pinned_u != 1:
        return fail(f"bash sha256sum pinned unique={pinned_u}")
    if unpin_u <= pinned_u:
        return fail(f"unpin unique {unpin_u} did not exceed pinned {pinned_u}")
    if pinned_var != 0.0:
        return fail(f"pinned token_sum variance={pinned_var}")
    if unpin_var <= pinned_var:
        return fail(f"token_sum variance did not increase ({unpin_var})")

    rec = doc.get("unpin_and_increase_control") or {}
    if rec.get("variance_increased") is not True:
        return fail("artifact control not increased")
    if int(rec.get("unique_transcript_sha256_count") or 0) <= 1:
        return fail("artifact unpin unique not >1")

    # Second-shell reproduction of the pinned unique count (tolerance 0).
    sh2 = shutil.which("sh")
    if sh2 and os.path.realpath(sh2) != os.path.realpath(shell):
        pinned_u_sh = unique_via_sha256sum("pinned", N, sh2)
        if pinned_u_sh != pinned_u:
            return fail(f"sh unique {pinned_u_sh} != {shell} unique {pinned_u}")
        second = sh2
    else:
        second = shell

    out = {
        "pass": True,
        "probe": "probe2-unpin-control",
        "pinned_unique_sha256sum": pinned_u,
        "unpinned_unique_sha256sum": unpin_u,
        "pinned_token_sum_variance": pinned_var,
        "unpinned_token_sum_variance": unpin_var,
        "shell": shell,
        "second_shell": second,
        "signal": "bash-sha256sum-and-token-sum",
        "unit_id": "RES-0094",
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"unpin unique {unpin_u} > pinned unique {pinned_u}; "
        f"token_sum var {unpin_var} > {pinned_var}"
    )
    print("SUCCESS:RES-0094-probe2 unpin-and-increase control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
