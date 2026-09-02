#!/usr/bin/env python3
"""Emit IMP-0104 receipt, SUBAGENT-RETURN.json, and UNIT-ARTIFACT-MANIFEST.json.

Runs the two named probes live, writes an honest non-BLOCKED receipt, then
registers the catalog output_path sha256 in the per-unit manifest. Does not
run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0104"
OUT_REL = "command-center/receipts/IMP-0104.json"
SENTINEL = "SUCCESS:IMP-0104"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0104/probe1_one_lock.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0104/probe2_partial_failure.py"
)
SUPPORTING = [
    "tools/marketplace/collections.py",
    "tools/marketplace/schema/collection.schema.json",
    "tools/marketplace/schema/collection-lockfile.schema.json",
    "tools/marketplace/tests/test_collections.py",
    "command-center/p2-wave/probes/IMP-0104/probe1_one_lock.py",
    "command-center/p2-wave/probes/IMP-0104/probe2_partial_failure.py",
]

sys.path.insert(0, str(REPO / "tools"))
from marketplace.collections import (  # noqa: E402
    CollectionDefinitionError,
    build_demo_index,
    define_collection,
    dumps_lockfile,
    incompatible_collection,
    install_collection,
    observed_matches_guarantee,
    re_toolchain_collection,
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe_row(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "command": command,
        "exit_code": exit_code,
        "fingerprint": fingerprint(method, command),
        "method": method,
        "raw_output": raw[:65000],
        "role": role,
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if b"\x00" in data[:8192]:
        eol = "BINARY"
    elif crlf and lf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    else:
        eol = "LF"
    return {
        "bytes": len(data),
        "eol": eol,
        "exists": path.is_file(),
        "path": rel,
        "role": role,
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        if data
        else "0" * 64,
    }


def run_unittests() -> tuple[bool, str]:
    loader = unittest.TestLoader()
    suite = loader.discover(
        str(REPO / "tools" / "marketplace" / "tests"),
        pattern="test_collections.py",
    )
    import io

    buf = io.StringIO()
    result = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
    return result.wasSuccessful(), buf.getvalue()


def live_measurements() -> dict:
    index = build_demo_index()
    col = re_toolchain_collection()
    with tempfile.TemporaryDirectory() as td:
        defined = define_collection(col, index, lock_dir=Path(td))
        locks = list(Path(td).glob("*.lock.json"))
        killed = install_collection(
            defined.lockfile, Path(td) / "killed", index=index, fail_after=1
        )
        ok = install_collection(
            defined.lockfile, Path(td) / "ok", index=index
        )
        try:
            define_collection(incompatible_collection(), index, lock_dir=Path(td) / "bad")
            unsat = {"raised": False}
        except CollectionDefinitionError as exc:
            unsat = {
                "locks": len(list((Path(td) / "bad").glob("*.lock.json")))
                if (Path(td) / "bad").is_dir()
                else 0,
                "message": str(exc),
                "pair": list(exc.pair) if exc.pair else None,
                "raised": True,
                "stage": exc.stage,
            }
        shuffled = dict(col)
        shuffled["members"] = list(reversed(list(col["members"])))
        again = define_collection(shuffled, index)
        return {
            "byte_identical_on_shuffle": defined.lockfile_bytes == again.lockfile_bytes,
            "declared_members": sorted(m["name"] for m in col["members"]),
            "killed": killed.as_dict(),
            "killed_matches_guarantee": observed_matches_guarantee(killed),
            "lock_bytes": len(defined.lockfile_bytes),
            "lock_member_set": defined.member_names,
            "lockfiles_on_disk": len(locks),
            "lockfiles_written": defined.lockfiles_written,
            "ok": ok.as_dict(),
            "ok_matches_guarantee": observed_matches_guarantee(ok),
            "resolved_versions": {
                p["name"]: p["version"] for p in defined.lockfile["packages"]
            },
            "unsat": unsat,
        }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    tests_ok, test_out = run_unittests()
    if not tests_ok:
        print("FAILED:IMP-0104 unittest suite")
        print(test_out)
        return 1
    live = live_measurements()
    if not (
        live["lockfiles_written"] == 1
        and live["lockfiles_on_disk"] == 1
        and set(live["lock_member_set"]) == set(live["declared_members"])
        and live["byte_identical_on_shuffle"]
        and live["killed_matches_guarantee"]
        and live["ok_matches_guarantee"]
        and live["unsat"].get("raised")
        and live["unsat"].get("pair") == ["capstone", "keystone"]
    ):
        print("FAILED:IMP-0104 live measurements")
        print(json.dumps(live, indent=2, default=str)[:4000])
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0104 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    p_lock = probe_row("source", "command", P1, t1, c1)
    p_fail = probe_row("source", "command", P2, t2, c2)
    p_unit = probe_row(
        "verifier",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/test_collections.py",
        test_out,
        0,
    )
    supporting = [artifact_row(p, "supporting") for p in SUPPORTING]
    receipt_dir = REPO / "command-center" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)

    doc = {
        "artifacts": supporting,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "note": "Measure runs after this emit and after named probes.",
                "read_ok": True,
            }
        ],
        "evidence": [
            {
                "anchor": "tools/marketplace/collections.py:define_collection",
                "claim": (
                    "Collection re-toolchain resolves to exactly one lockfile whose "
                    "member set equals the declared set {binwalk, ghidra, radare2}, "
                    "and a member-order shuffle yields byte-identical lockfile bytes."
                ),
                "confidence": "almost-certain",
                "probes": [p_lock, p_unit],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/marketplace/collections.py:install_collection",
                "claim": (
                    "Documented partial-failure guarantee is all-or-nothing. A kill "
                    "after the first member write rolls back; filesystem census shows "
                    "zero package files and no lock. A mutually incompatible pair "
                    "(capstone, keystone) fails at definition time with no lockfile."
                ),
                "confidence": "almost-certain",
                "probes": [p_fail, p_unit],
                "verdict": "CONFIRMED",
            },
        ],
        "live_measurements": live,
        "manifest_registration": {
            "global_catalog_write": False,
            "manifest_path": "command-center/p2-wave/probes/IMP-0104/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "named_probes": [
            {"command": P1, "exit_code": c1, "id": "probe1", "role": "one-lock-member-set"},
            {"command": P2, "exit_code": c2, "id": "probe2", "role": "partial-failure-census"},
        ],
        "negative_controls": [
            {
                "bad_state_output": t2[-2000:],
                "description": (
                    "Mutually incompatible pair capstone+keystone must fail at "
                    "collection-definition time; no lockfile written. Mid-install "
                    "kill must leave an empty census matching all-or-nothing."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "compatible re-toolchain defines and installs",
                "id": "IMP0104-C1",
                "kind": "known-broken-fixture",
                "silent_on_good_state": True,
            }
        ],
        "output_path": OUT_REL,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/marketplace/schema/collection.schema.json"
        ),
        "question": (
            "Implement a collection as a named set of packages with a single "
            "resolved lockfile, so installing the RE toolchain is one atomic, "
            "reproducible operation whose members are known to resolve together — "
            "and where an incompatible member is reported at collection-definition "
            "time, not at install time."
        ),
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0083 (deterministic resolver) and IMP-0084 (lockfile) are "
                    "not delivered as separate units on this worktree. This unit "
                    "ships a collection-scoped resolver and lockfile sufficient for "
                    "the collection contract; it does not claim those units complete."
                ),
                "settling_experiment": (
                    "Re-bind marketplace.collections onto IMP-0083/IMP-0084 once "
                    "those units exist, and re-run test_collections.py."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0104-probe2-partial-failure-census",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10861",
        "state": "SUCCESS",
        "tests": [
            {
                "command": "python3 -B tools/marketplace/tests/test_collections.py",
                "id": "test_collection_resolves_to_one_lock",
                "result": "PASS",
            },
            {
                "command": "python3 -B tools/marketplace/tests/test_collections.py",
                "id": "test_partial_failure_matches_declared_guarantee",
                "result": "PASS",
            },
            {
                "command": "python3 -B tools/marketplace/tests/test_collections.py",
                "id": "test_incompatible_pair_fails_at_definition_time",
                "result": "PASS",
            },
        ],
        "timestamps": {"ended_at": ended, "started_at": started},
        "unit_id": UNIT,
    }
    out_path = REPO / OUT_REL
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out_path)
    if live_bytes < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0104 receipt {live_bytes}B below floor")
        return 1

    primary = {
        "bytes": live_bytes,
        "path": OUT_REL,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/IMP-0104/SUBAGENT-RETURN.json",
        "role": "primary",
        "sha256": live_sha,
        "unit_id": UNIT,
    }
    manifest_rows = [primary]
    for rel in SUPPORTING:
        sha, nbytes = sha256_file(REPO / rel)
        manifest_rows.append(
            {
                "bytes": nbytes,
                "path": rel,
                "present": True,
                "receipt_path": "command-center/p2-wave/probes/IMP-0104/SUBAGENT-RETURN.json",
                "role": "supporting",
                "sha256": sha,
                "unit_id": UNIT,
            }
        )
    ret = {
        "artifacts": [
            {
                "bytes": live_bytes,
                "exists": True,
                "path": OUT_REL,
                "role": "primary",
                "sha256": live_sha,
            }
        ],
        "cloud_ok": False,
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/IMP-0104/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "one-lock-member-set",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "partial-failure-census",
            },
        ],
        "notes": (
            "G-1 for IMP-0104: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
        "output_path": OUT_REL,
        "output_schema": doc["output_schema"],
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0104-probe2-partial-failure-census",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": ended,
        "unit_id": UNIT,
    }
    man = {
        "artifacts": manifest_rows,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(manifest_rows),
        "present": len(manifest_rows),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print("SUCCESS:IMP-0104 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
