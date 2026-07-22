"""Harvest fan-out artifacts from DBFS and apply the completeness gate.

Download uses `databricks fs cat`, never `fs cp`. `fs cp` has been observed to be a silent no-op
against these paths — it returns 0 having written nothing, so a harvest built on it reports a full
set of empty files and every downstream count is wrong in the safe-looking direction.

Terminal states are explicit per unit (SUCCESS / SEVERED / MALFORMED / ABSENT) rather than a
boolean, because "did not arrive" and "arrived broken" need different follow-up: the first is
re-runnable, the second usually means the prompt contract is wrong.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gate import gate  # noqa: E402


def _env(config_file: str | None) -> dict[str, str]:
    """Environment for the CLI.

    A stale DATABRICKS_TOKEN in the ambient environment OVERRIDES the config file and produces
    confusing 403s, so the token/host vars are stripped and auth is pinned to the config file.
    MSYS_NO_PATHCONV is set because Git-Bash rewrites `dbfs:/...`-style arguments into Windows
    paths before the CLI ever sees them.
    """
    env = dict(os.environ)
    for k in ("DATABRICKS_TOKEN", "DATABRICKS_HOST", "DATABRICKS_ACCOUNT_ID"):
        env.pop(k, None)
    if config_file:
        env["DATABRICKS_CONFIG_FILE"] = config_file
    env["MSYS_NO_PATHCONV"] = "1"
    return env


def _cli(
    args: list[str], env: dict[str, str], timeout: int = 180
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["databricks", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
    )


def harvest(
    result_dir: str,
    dest: pathlib.Path,
    *,
    config_file: str | None = None,
    fence: str | None = None,
    required_fields: tuple[str, ...] = (),
    expected: int | None = None,
) -> dict:
    env = _env(config_file)
    dest.mkdir(parents=True, exist_ok=True)

    listing = _cli(["fs", "ls", result_dir], env)
    names = [
        ln.split("/")[-1].split()[-1]
        for ln in listing.stdout.splitlines()
        if ln.strip().endswith(".md")
    ]

    states: dict[str, str] = {}
    for name in names:
        cat = _cli(["fs", "cat", f"{result_dir}/{name}"], env)
        text = cat.stdout
        (dest / name).write_bytes(text.encode("utf-8", errors="replace"))
        unit_id = name[:-3]
        r = gate(text, unit_id, fence=fence, required_fields=required_fields)
        if r.ok:
            states[unit_id] = "SUCCESS"
        elif "sentinel" in r.reason:
            states[unit_id] = "SEVERED"  # process ended; artifact never completed
        else:
            states[unit_id] = "MALFORMED"  # arrived, but violates the output contract

    census = Counter(states.values())
    out = {
        "result_dir": result_dir,
        "downloaded": len(names),
        "expected": expected,
        "census": dict(census),
        "states": states,
        "missing_count": (expected - len(names)) if expected is not None else None,
    }
    if expected is not None and len(names) != expected:
        # Absence is a first-class terminal state; a silent short harvest is how a wave gets
        # declared complete while units are still missing.
        out["ABSENT_WARNING"] = (
            f"expected {expected} artifacts, downloaded {len(names)}"
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--result-dir", required=True, help="e.g. dbfs:/tmp/<tag>/results")
    ap.add_argument("--dest", required=True, type=pathlib.Path)
    ap.add_argument("--config-file")
    ap.add_argument(
        "--fence", help="fenced block name the contract requires, e.g. 'verdict'"
    )
    ap.add_argument("--required-field", action="append", default=[])
    ap.add_argument("--expected", type=int)
    a = ap.parse_args()

    res = harvest(
        a.result_dir,
        a.dest,
        config_file=a.config_file,
        fence=a.fence,
        required_fields=tuple(a.required_field),
        expected=a.expected,
    )
    print(json.dumps({k: v for k, v in res.items() if k != "states"}, indent=1))
    for state in ("SEVERED", "MALFORMED"):
        bad = [u for u, s in res["states"].items() if s == state]
        if bad:
            print(f"  {state}: {bad[:20]}")
    return (
        0
        if res["census"].get("SUCCESS", 0) == res["downloaded"]
        and not res.get("ABSENT_WARNING")
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
