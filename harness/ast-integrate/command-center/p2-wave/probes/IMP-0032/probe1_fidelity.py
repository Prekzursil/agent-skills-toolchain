#!/usr/bin/env python3
"""Probe 1: dry-run plan equals real-run journal; census is unchanged under dry-run.

Signal 1: execute(dry_run=True).mutations vs execute(dry_run=False).journal.
Signal 2: an independent hashlib walk (not plugin.census) of the throwaway HOME
is identical before vs after dry-run, and the observed mutation set after the
real run matches the dry-run plan.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "plugin" / "tests"))

from test_dry_run_fidelity import run_suite  # noqa: E402

from plugin.execute import execute  # noqa: E402
from plugin.mutations import fingerprints  # noqa: E402
from plugin.scenario import seed_home, write_payload  # noqa: E402


def independent_walk(root: Path) -> dict[str, dict]:
    root = root.resolve()
    out: dict[str, dict] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        data = path.read_bytes()
        rel = path.relative_to(root).as_posix()
        out[rel] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return out


def walk_records(before: dict, after: dict) -> list[dict]:
    recs: list[dict] = []
    for path in set(before) | set(after):
        b = before.get(path)
        a = after.get(path)
        if b == a:
            continue
        if b is None:
            recs.append(
                {
                    "op": "create",
                    "path": path,
                    "before_bytes": 0,
                    "after_bytes": a["bytes"],
                    "byte_delta": a["bytes"],
                    "before_sha256": None,
                    "after_sha256": a["sha256"],
                }
            )
        elif a is None:
            recs.append(
                {
                    "op": "delete",
                    "path": path,
                    "before_bytes": b["bytes"],
                    "after_bytes": 0,
                    "byte_delta": -b["bytes"],
                    "before_sha256": b["sha256"],
                    "after_sha256": None,
                }
            )
        else:
            recs.append(
                {
                    "op": "overwrite",
                    "path": path,
                    "before_bytes": b["bytes"],
                    "after_bytes": a["bytes"],
                    "byte_delta": a["bytes"] - b["bytes"],
                    "before_sha256": b["sha256"],
                    "after_sha256": a["sha256"],
                }
            )
    return recs


def main() -> int:
    suite = run_suite()
    if not suite.get("pass"):
        print("FAILED:IMP-0032-probe1 suite did not pass")
        return 1
    for cmd in suite["commands"]:
        row = suite["per_command"][cmd]
        if not row.get("plan_eq_journal") or not row.get("census_unchanged_on_dry_run"):
            print(f"FAILED:IMP-0032-probe1 {cmd} missing fidelity")
            return 1
    if not suite["hidden_write"].get("caught"):
        print("FAILED:IMP-0032-probe1 hidden write not caught")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0032-p1-") as tmp:
        scratch = Path(tmp)
        home = seed_home(scratch / "home")
        source = write_payload(scratch, "1.0.0")
        before_dry = independent_walk(home)
        dry = execute("install", home, source, dry_run=True)
        after_dry = independent_walk(home)
        if before_dry != after_dry:
            print("FAILED:IMP-0032-probe1 independent walk changed under dry-run")
            print(json.dumps({"before": before_dry, "after": after_dry}, indent=2)[:2000])
            return 1
        before = independent_walk(home)
        real = execute("install", home, source, dry_run=False)
        after = independent_walk(home)
        if fingerprints(dry.mutations) != fingerprints(real.journal):
            print("FAILED:IMP-0032-probe1 dry-run plan != journal")
            return 1
        observed = fingerprints(walk_records(before, after))
        planned = fingerprints(dry.mutations)
        if observed != planned:
            print("FAILED:IMP-0032-probe1 independent walk != dry-run plan")
            print(
                json.dumps(
                    {
                        "planned": sorted(map(str, planned)),
                        "observed": sorted(map(str, observed)),
                    },
                    indent=2,
                )[:4000]
            )
            return 1

    summary = {
        "probe": "probe1-fidelity",
        "unit_id": "IMP-0032",
        "commands": list(suite["commands"]),
        "per_command_counts": {
            cmd: {
                "dry": suite["per_command"][cmd]["dry_run_mutations"],
                "journal": suite["per_command"][cmd]["journal_mutations"],
            }
            for cmd in suite["commands"]
        },
        "negative_control_dry_run_census_zero": True,
        "independent_walk_dry_run_unchanged": True,
        "independent_walk_eq_plan": True,
        "hidden_write_caught": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "independent_walk_dry_run_unchanged=True hidden_write_caught=True "
        f"commands={len(suite['commands'])}"
    )
    print("SUCCESS:IMP-0032-probe1 dry-run fidelity and census negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
