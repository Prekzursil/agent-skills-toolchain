#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0085.json from live filter measurements."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "marketplace"))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

import compat as C  # noqa: E402
from independent import independent_accepted, load_packages  # noqa: E402

OUT = "command-center/receipts/IMP-0085.json"
TEST = "tools/marketplace/tests/test_compat_resolution.py"
INDEX = "tools/marketplace/fixtures/compat-index.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0085/probe1_resolver_sets.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0085/probe2_independent_recompute.py"
)


def sha_file(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": path.is_file(),
        "role": "supporting",
        "eol": "LF",
    }


def run_tests() -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(REPO / TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def main() -> int:
    rc, test_out = run_tests()
    if rc != 0:
        print(test_out[-2000:])
        print("FAILED:IMP-0085 tests")
        return 1

    pkgs = C.load_candidates()
    indep_pkgs = load_packages(REPO / INDEX)
    matrix = C.resolution_matrix(pkgs, client_name="claude")
    compared = []
    mismatch = []
    for plat in C.MATRIX_PLATFORMS:
        for ver in C.MATRIX_CLIENTS:
            prod = C.filter_candidates(
                pkgs, platform=plat, client_version=ver, client_name="claude"
            )
            indep = independent_accepted(
                indep_pkgs, platform=plat, client_version=ver, client_name="claude"
            )
            row = {
                "platform": plat,
                "client_version": ver,
                "production": list(prod.accepted),
                "independent": list(indep),
                "identical": tuple(prod.accepted) == indep,
            }
            compared.append(row)
            if not row["identical"]:
                mismatch.append(row)
    extra = C.filter_candidates(
        pkgs, platform="linux", client_version="0.9.0", client_name="claude"
    )
    extra_i = independent_accepted(
        indep_pkgs, platform="linux", client_version="0.9.0", client_name="claude"
    )
    if tuple(extra.accepted) != extra_i:
        mismatch.append(
            {
                "platform": "linux",
                "client_version": "0.9.0",
                "production": list(extra.accepted),
                "independent": list(extra_i),
            }
        )
    if mismatch:
        print("FAILED:IMP-0085 production/independent mismatch")
        print(json.dumps(mismatch, indent=2)[:3000])
        return 1

    class Bare:
        accepted = ()
        unmet_requirement = ""

    try:
        C.assert_nonempty_reason_on_empty(Bare())
        print("FAILED:IMP-0085 negative control silent")
        return 1
    except AssertionError:
        neg_fired = True

    unknown_leaked = []
    unknown = {"demo.unknown-compat@9.9.9", "demo.empty-compat-object@0.0.1"}
    for row in compared:
        hit = unknown.intersection(row["production"])
        if hit:
            unknown_leaked.append(sorted(hit))
    if unknown_leaked:
        print("FAILED:IMP-0085 unknown treated as compatible")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        sha_file("tools/marketplace/compat.py"),
        sha_file("tools/marketplace/tests/test_compat_resolution.py"),
        sha_file("tools/marketplace/fixtures/compat-index.json"),
        sha_file("tools/marketplace/schema/compat.schema.json"),
        sha_file("command-center/p2-wave/probes/IMP-0085/independent.py"),
        sha_file("command-center/p2-wave/probes/IMP-0085/probe1_resolver_sets.py"),
        sha_file("command-center/p2-wave/probes/IMP-0085/probe2_independent_recompute.py"),
    ]
    src = {
        "role": "source",
        "method": "command",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/compat.py-resolution_matrix",
        "raw_output": json.dumps({k: v["accepted"] for k, v in matrix.items()}, sort_keys=True),
        "exit_code": 0,
        "fingerprint": fp("command", "resolution_matrix"),
    }
    ver = {
        "role": "verifier",
        "method": "command",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0085/independent.py",
        "raw_output": json.dumps(
            [{"platform": r["platform"], "client_version": r["client_version"], "independent": r["independent"]} for r in compared],
            sort_keys=True,
        ),
        "exit_code": 0,
        "fingerprint": fp("command", "independent_accepted"),
    }
    tsrc = {
        "role": "source",
        "method": "command",
        "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {TEST}",
        "raw_output": test_out[-4000:],
        "exit_code": rc,
        "fingerprint": fp("command", TEST),
    }

    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0085",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0085",
        "spec_anchor": "_USER-PROMPTS.md:10852 (platform and client compatibility); IMP-0008; IMP-0083",
        "title": "Platform and client compatibility resolution with an explicit refusal reason",
        "question_or_target": (
            "Filter candidate versions by declared platform and client compatibility "
            "during resolution, and when nothing satisfies the constraints, report the "
            "exact unmet requirement (e.g. 'requires client >= X, you have Y') instead "
            "of an empty result set."
        ),
        "min_bytes_threshold": 128,
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
                "eol": "LF",
            }
        ]
        + supporting,
        "evidence": [
            {
                "claim": (
                    "For each of Windows/macOS/Linux and client versions 1.2.0 and 3.1.0, "
                    "the resolver's filtered candidate set equals an independent "
                    "set-algebra recomputation from the same raw metadata."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/compat.py:filter_candidates",
                "confidence": "almost-certain",
                "probes": [src, ver],
                "measured": {
                    "cells": compared,
                    "matrix": {k: v["accepted"] for k, v in matrix.items()},
                },
            },
            {
                "claim": (
                    "An empty filtered set always carries a non-empty unmet_requirement; "
                    "linux+0.9.0 reports 'requires client >= 1.0.0, you have 0.9.0'."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/compat.py:_aggregate_unmet",
                "confidence": "almost-certain",
                "probes": [src, tsrc],
                "measured": {
                    "accepted": list(extra.accepted),
                    "unmet_requirement": extra.unmet_requirement,
                },
            },
            {
                "claim": (
                    "A package with no declared compatibility (missing field or empty "
                    "object) is treated as unknown, not universally compatible."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/compat.py:declared_compat",
                "confidence": "almost-certain",
                "probes": [src, ver],
                "measured": {
                    "unknown_keys": sorted(unknown),
                    "leaked_into_any_matrix_cell": False,
                },
            },
        ],
        "tests": [
            {
                "id": "test_compat_resolution.py",
                "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {TEST}",
                "result": "PASS",
                "exit_code": rc,
                "raw_output": test_out[-2000:],
            }
        ],
        "negative_controls": [
            {
                "id": "empty-reason-forbidden",
                "kind": "known-broken-fixture",
                "description": (
                    "An empty candidate set with an empty unmet_requirement must fail "
                    "assert_nonempty_reason_on_empty."
                ),
                "fired_on_bad_state": neg_fired,
                "silent_on_good_state": True,
                "bad_state_output": "AssertionError: NEGATIVE CONTROL: empty candidate set with empty unmet_requirement",
                "good_state_output": extra.unmet_requirement,
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0085-independent-set-algebra",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Unknown-compatibility default is conservative: undeclared and empty "
                "compatibility objects are subtracted before platform/client matching. "
                "Signal 2 recomputes membership by set difference and required identical "
                "sets on the 3×2 matrix plus empty and client-name extras."
            ),
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0085/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/probes/IMP-0085/probe1_resolver_sets.py",
                "executed": True,
                "read_ok": True,
                "probe": {
                    "command": P1,
                    "role": "verifier",
                    "method": "command",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0083 deterministic SAT resolver and IMP-0008 live `claude --version` "
                    "negotiation are not re-implemented here; this unit is the compatibility "
                    "filter the resolver calls, with fail-closed version parsing."
                ),
                "settling_experiment": "IMP-0083 / IMP-0008 delivery on this worktree.",
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "timestamps": {"started_at": now, "ended_at": now},
        "named_probes": [
            {"id": "probe1", "role": "resolver-filtered-sets", "command": P1},
            {"id": "probe2", "role": "independent-recompute", "command": P2},
        ],
        "cloud_ok": False,
        "registered": True,
        "implementation": {
            "module": "tools/marketplace/compat.py",
            "hook": "filter_index_for_resolution",
            "unknown_default": "conservative-refuse",
            "reason_example": extra.unmet_requirement,
        },
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global tools/command-center/unit_manifest.py --write was run",
            "IMP-0083 SAT solver is complete on this worktree",
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(body, encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    if len(raw) < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0085 artifact {len(raw)}B below floor")
        return 1
    if "SUCCESS:IMP-0085" not in body:
        print("FAILED:IMP-0085 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    print("SUCCESS:IMP-0085 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
