#!/usr/bin/env python3
"""Version-bump gate: reject a declared bump that is lower than the required bump.

The required bump is computed by the ARC-0092 classifier (diff of two artifacts).
This unit is the conformance suite written before a broad REL-0001 linter; the
gate here is the executable policy those tests bind to.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center/p2-wave/probes/ARC-0092"))

import calculator as C  # noqa: E402

RANK = C.RANK
ACCEPT, REJECT = "ACCEPT", "REJECT"


def bump_from_semver(old_s: str, new_s: str) -> str:
    def parts(s: str) -> tuple[int, int, int]:
        core = s.strip().split("+", 1)[0].split("-", 1)[0]
        bits = core.split(".")
        if len(bits) < 3:
            raise ValueError(f"semver needs MAJOR.MINOR.PATCH, got {s!r}")
        return int(bits[0]), int(bits[1]), int(bits[2])

    old, new = parts(old_s), parts(new_s)
    if new[0] != old[0]:
        return "MAJOR" if new[0] > old[0] else "NONE"
    if new[1] != old[1]:
        return "MINOR" if new[1] > old[1] else "NONE"
    if new[2] != old[2]:
        return "PATCH" if new[2] > old[2] else "NONE"
    return "NONE"


def evaluate(
    old: Any,
    new: Any,
    artifact_class: str,
    declared: str,
) -> dict:
    if declared not in RANK:
        raise ValueError(f"unknown declared bump {declared!r}")
    verdict = C.classify(old, new, artifact_class)
    required = verdict["required_bump"]
    if RANK[declared] < RANK[required]:
        decision, code = REJECT, 2
    else:
        decision, code = ACCEPT, 0
    return {
        "artifact_class": artifact_class,
        "declared_bump": declared,
        "required_bump": required,
        "decision": decision,
        "exit_code": code,
        "computed_not_asserted": True,
        "change_count": verdict["change_count"],
        "changes": verdict["changes"],
        "kinds": [row["kind"] for row in verdict["changes"]],
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TST-0046 version-bump gate")
    p.add_argument("--old", required=True, type=Path)
    p.add_argument("--new", required=True, type=Path)
    p.add_argument(
        "--class",
        dest="artifact_class",
        required=True,
        choices=sorted(C.CLASSIFIERS),
    )
    p.add_argument("--declared", choices=sorted(RANK), default=None)
    p.add_argument("--from-version", dest="from_version", default=None)
    p.add_argument("--to-version", dest="to_version", default=None)
    args = p.parse_args(argv)
    declared = args.declared
    if args.from_version and args.to_version:
        derived = bump_from_semver(args.from_version, args.to_version)
        if declared is None:
            declared = derived
        elif declared != derived:
            print(
                json.dumps(
                    {
                        "error": "declared-vs-semver-mismatch",
                        "declared": declared,
                        "from_semver": derived,
                    }
                )
            )
            return 1
    if declared is None:
        print("FAILED:TST-0046-gate need --declared or --from-version/--to-version")
        return 1
    result = evaluate(
        load_json(args.old),
        load_json(args.new),
        args.artifact_class,
        declared,
    )
    if args.from_version:
        result["from_version"] = args.from_version
        result["to_version"] = args.to_version
    print(json.dumps(result, sort_keys=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
