#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0084.json from live lockfile measurements."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from marketplace.lockfile import (  # noqa: E402
    CURRENT_RESOLVER_VERSION,
    DigestMismatch,
    MissingLockfileEntry,
    filesystem_census,
    generate_lockfile,
    install_verified,
    load_lockfile,
    sha256_hex,
)
from scenario import blob_map, sample_packages  # noqa: E402

OUT = "command-center/receipts/IMP-0084.json"
LIB = "tools/marketplace/lockfile.py"
SCHEMA = "tools/marketplace/schema/lockfile.schema.json"
TEST = "tools/marketplace/tests/test_lockfile.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0084/probe1_mismatch_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0084/probe2_determinism_reviewer.py"
)
QUESTION = (
    "Define the lockfile (resolved versions, digests, source URLs, resolver "
    "version) and enforce it at install: a package whose fetched digest "
    "differs from the lockfile entry is refused, so a mutated upstream cannot "
    "substitute content under a pinned version."
)


def digest_rel(rel: str) -> tuple[str, int, bool]:
    path = REPO / rel
    if not path.is_file():
        return "", 0, False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), True


def art(rel: str, role: str) -> dict:
    sha, size, exists = digest_rel(rel)
    return {
        "path": rel,
        "sha256": sha or ("0" * 64),
        "bytes": size,
        "exists": exists,
        "role": role,
        "eol": "LF",
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def live_mismatch_and_census() -> dict:
    packages = sample_packages()
    blobs = blob_map(packages)
    lock_bytes = generate_lockfile(packages)
    lock_again = generate_lockfile(list(reversed(packages)))
    pkg = packages[0]
    mutated = pkg.blob + b"\x00mutated"
    with tempfile.TemporaryDirectory(prefix="imp0084-emit-") as tmp:
        dest = Path(tmp)
        marker = dest / "keep.txt"
        marker.write_text("keep\n", encoding="utf-8")
        before = filesystem_census(dest)
        fetch_n = {"n": 0}

        def fetch_bad(url: str) -> bytes:
            fetch_n["n"] += 1
            return mutated

        try:
            install_verified(lock_bytes, name=pkg.name, dest=dest, fetch=fetch_bad)
            mismatch = {"raised": False}
        except DigestMismatch as err:
            mismatch = {
                "raised": True,
                "named": "digest mismatch" in str(err).lower(),
                "message": str(err),
                "expected_hex": err.expected_hex,
                "actual_hex": err.actual_hex,
                "dest_unchanged": err.dest_unchanged()
                and filesystem_census(dest) == before,
                "fetch_count": err.fetch_count,
                "wrote_payload": (dest / pkg.name / pkg.version / "payload").exists(),
            }

        def fetch_ok(url: str) -> bytes:
            return blobs[url]

        ok = install_verified(lock_bytes, name=pkg.name, dest=dest, fetch=fetch_ok)
        try:
            install_verified(
                lock_bytes, name="ghost", dest=dest, fetch=lambda u: b"nope"
            )
            missing = {"raised": False}
        except MissingLockfileEntry as err:
            missing = {
                "raised": True,
                "fetch_count": err.fetch_count,
                "named": "missing lockfile entry" in str(err).lower(),
            }
        stale_bytes = generate_lockfile(
            packages, resolver_version="marketplace-resolver/0.9.0"
        )
        stale = install_verified(
            stale_bytes,
            name=packages[1].name,
            dest=dest,
            fetch=fetch_ok,
            current_resolver_version=CURRENT_RESOLVER_VERSION,
        )
    doc = load_lockfile(lock_bytes)
    return {
        "lockfile_bytes": len(lock_bytes),
        "lockfile_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "deterministic": lock_bytes == lock_again,
        "resolver_version": doc["resolver_version"],
        "package_count": len(doc["packages"]),
        "mismatch": mismatch,
        "negative_control_installed": ok.digest_hex == sha256_hex(pkg.blob),
        "missing": missing,
        "stale_warnings": stale.warnings,
        "fetch_n_mismatch": fetch_n["n"],
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    test_rc, test_out = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/test_lockfile.py -v"
    )
    if test_rc != 0:
        print("FAILED:IMP-0084 tests")
        print(test_out[-3000:])
        return 1
    live = live_mismatch_and_census()
    if not (
        live["deterministic"]
        and live["mismatch"].get("raised")
        and live["mismatch"].get("named")
        and live["mismatch"].get("dest_unchanged")
        and not live["mismatch"].get("wrote_payload")
        and live["negative_control_installed"]
        and live["missing"].get("raised")
        and live["missing"].get("fetch_count") == 0
        and live["stale_warnings"]
    ):
        print("FAILED:IMP-0084 emit live measurements")
        print(json.dumps(live, indent=2)[:4000])
        return 1

    p1_rc, p1_out = run_cmd(P1)
    p2_rc, p2_out = run_cmd(P2)
    if p1_rc != 0 or p2_rc != 0:
        print("FAILED:IMP-0084 emit probes", p1_rc, p2_rc)
        print(p1_out[-1500:])
        print(p2_out[-1500:])
        return 1

    supporting = [
        SCHEMA,
        TEST,
        "command-center/p2-wave/probes/IMP-0084/scenario.py",
        "command-center/p2-wave/probes/IMP-0084/probe1_mismatch_census.py",
        "command-center/p2-wave/probes/IMP-0084/probe2_determinism_reviewer.py",
    ]
    artifacts = [art(LIB, "primary-implementation")] + [
        art(p, "supporting") for p in supporting
    ]
    missing_art = [a["path"] for a in artifacts if not a["exists"]]
    if missing_art:
        print("FAILED:IMP-0084 emit missing artifacts", missing_art)
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0084",
        "id": "IMP-0084",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0084",
        "completion_sentinel": "SUCCESS:IMP-0084",
        "title": "Lockfile format with integrity hashes and verify-on-install",
        "question_or_target": QUESTION,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/marketplace/schema/lockfile.schema.json"
        ),
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "implementation": {
            "module": LIB,
            "schema": SCHEMA,
            "tests": TEST,
            "lockfile_fields": [
                "lockfile_version",
                "resolver_version",
                "packages[].name",
                "packages[].version",
                "packages[].source_url",
                "packages[].digest.algorithm",
                "packages[].digest.hex",
            ],
            "digest_algorithm": "sha256",
            "current_resolver_version": CURRENT_RESOLVER_VERSION,
            "verify_before_write": True,
            "retry_on_digest_mismatch": False,
            "missing_entry_fetches": False,
            "stale_resolver_action": "warn-and-still-enforce-digest",
            "canonical_json": "sort_keys + compact separators + trailing newline",
        },
        "live": live,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "An install of a mutated upstream blob is refused with a "
                    "message that names the digest mismatch (expected vs actual "
                    "sha256) and fetch_count==1 (no retry)."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:install_verified",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": p1_rc,
                        "raw_output": p1_out[:8000],
                    }
                ],
            },
            {
                "claim": (
                    "Filesystem census of the install destination is unchanged "
                    "across the mismatch refusal: no payload path is created. "
                    "Refusing after a partial extract is not this implementation."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:filesystem_census",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": p1_rc,
                        "raw_output": p1_out[:4000],
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "test_lockfile.py",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "tools/marketplace/tests/test_lockfile.py -v"
                ),
                "exit_code": test_rc,
                "result": "PASS",
                "detail": test_out[-2500:],
            },
            {
                "id": "probe1-mismatch-census",
                "command": P1,
                "exit_code": p1_rc,
                "result": "PASS",
            },
            {
                "id": "probe2-determinism-reviewer",
                "command": P2,
                "exit_code": p2_rc,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "unmutated-blob-installs-in-same-run",
                "kind": "both-states",
                "description": (
                    "After mismatch refuse, the honest blob installs in the "
                    "same process so a refuse-only stub cannot go green."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "missing-entry-does-not-fetch",
                "kind": "both-states",
                "description": "Unpinned name refuses with fetch_count==0.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0084-probe2-determinism-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Reviewer mutation is XOR of the first payload byte (distinct "
                "from probe 1's suffix mutation). Refusal occurred before any "
                "destination write. Catalog reviewer_requirement is satisfied "
                "by this independent mutation, not by a second human vendor."
            ),
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "no retry on a digest mismatch; that is a security event",
        },
        "notes": (
            "G-1 IMP-0084: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "IMP-0083 resolver is a declared dependency and is not reimplemented "
            "here; this unit consumes a resolved index snapshot. SUCCESS:IMP-0084"
        ),
        "profile": "p2-wave-g1-unit",
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print("SUCCESS:IMP-0084 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
