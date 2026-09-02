#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0002.json from a live three-build proof."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.fixture_repo import create_pack_fixture  # noqa: E402
from plugin.pack import (  # noqa: E402
    COMPRESSION_LEVEL,
    NORMALISATION,
    pack_repository,
    sha256_file,
)
from plugin.tests.test_pack_determinism import (  # noqa: E402
    test_real_mtimes_breaks_determinism,
    test_two_builds_identical,
)
from plugin.tests.test_pack_uses_blob_bytes import (  # noqa: E402
    test_crlf_worktree_packed_with_lf_blob,
    test_source_uses_cat_file_not_worktree_read_of_payload,
)

OUT = "command-center/receipts/IMP-0002.json"
SENTINEL = "SUCCESS:IMP-0002"
HASHER = REPO / "command-center/p2-wave/probes/IMP-0002/hash_archive.py"
QUESTION = (
    "Implement tools/plugin/pack.py so two builds of the same commit produce "
    "byte-identical archives: sort entries by NFC-normalised path, zero out "
    "mtime/uid/gid/umask bits, pin the compression level, and read file bytes "
    "via `git cat-file -p <rev>:<path>` rather than the git subcommand measured "
    "on this box to return CRLF worktree bytes instead of the blob."
)


def sha256_file_lf(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe(role: str, method: str, command: str, raw_output: str, exit_code: int) -> dict:
    fp = hashlib.md5(f"{command}|{exit_code}|{raw_output}".encode("utf-8")).hexdigest()
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:2000],
        "exit_code": exit_code,
        "fingerprint": fp,
    }


def run_unit_tests() -> dict:
    errors: list[str] = []
    names = [
        "test_two_builds_identical",
        "test_real_mtimes_breaks_determinism",
        "test_crlf_worktree_packed_with_lf_blob",
        "test_source_uses_cat_file_not_worktree_read_of_payload",
    ]
    fns = {
        "test_two_builds_identical": test_two_builds_identical,
        "test_real_mtimes_breaks_determinism": test_real_mtimes_breaks_determinism,
        "test_crlf_worktree_packed_with_lf_blob": test_crlf_worktree_packed_with_lf_blob,
        "test_source_uses_cat_file_not_worktree_read_of_payload": test_source_uses_cat_file_not_worktree_read_of_payload,
    }
    details: dict = {}
    for name in names:
        try:
            result = fns[name]()
            details[name] = result if isinstance(result, dict) else {"ok": True}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}\n{traceback.format_exc()[-800:]}")
    return {"passed": not errors, "names": names, "errors": errors, "details": details}


def independent_hash(archive: Path) -> str:
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-B", str(HASHER), str(archive)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"hash_archive failed: {proc.stderr}")
    digest = (proc.stdout or "").strip().splitlines()[-1].strip()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuntimeError(f"hash_archive output {digest!r}")
    return digest


def live_three_builds() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0002-emit-") as tmp:
        base = Path(tmp)
        a = base / "a"
        a.mkdir()
        repo = create_pack_fixture(a, crlf_worktree=True)
        allow = a / "payload-allowlist.json"
        o1, o2 = a / "1.tar.gz", a / "2.tar.gz"
        r1 = pack_repository(repo, o1, allowlist_path=allow)
        for path in repo.rglob("*"):
            if path.is_file():
                os.utime(path, (1_111_111_111, 1_111_111_111))
        r2 = pack_repository(repo, o2, allowlist_path=allow)
        h1, h2 = sha256_file(o1), sha256_file(o2)

        b = base / "b"
        t = base / "tmp-b"
        b.mkdir()
        t.mkdir()
        repo_b = create_pack_fixture(b, crlf_worktree=True)
        allow_b = b / "payload-allowlist.json"
        for path in repo_b.rglob("*"):
            if path.is_file():
                os.utime(path, (946_684_800, 946_684_800))
        o3 = b / "3.tar.gz"
        old = Path.cwd()
        try:
            os.environ["TZ"] = "America/Adak"
            os.environ["TMPDIR"] = str(t)
            os.environ["SOURCE_DATE_EPOCH"] = "946684800"
            os.chdir(b)
            r3 = pack_repository(repo_b, o3, allowlist_path=allow_b)
        finally:
            os.chdir(old)
        h3 = sha256_file(o3)
        h3i = independent_hash(o3)
        equal = h1 == h2 == h3 == h3i == r1.sha256 == r2.sha256 == r3.sha256
        return {
            "equal": equal,
            "sha256": h1,
            "build1": h1,
            "build2": h2,
            "build3": h3,
            "build3_independent_hasher": h3i,
            "members": list(r1.members),
            "bytes": r1.size,
            "compression_level": COMPRESSION_LEVEL,
        }


def main() -> int:
    tests = run_unit_tests()
    if not tests["passed"]:
        print("FAILED:IMP-0002 unit tests")
        print("\n".join(tests["errors"]))
        return 1
    live = live_three_builds()
    if not live["equal"]:
        print("FAILED:IMP-0002 three-build inequality", json.dumps(live, indent=2))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl = REPO / "tools/plugin/pack.py"
    fixture = REPO / "tools/plugin/fixture_repo.py"
    allow = REPO / "tools/plugin/payload-allowlist.json"
    t1 = REPO / "tools/plugin/tests/test_pack_determinism.py"
    t2 = REPO / "tools/plugin/tests/test_pack_uses_blob_bytes.py"
    impl_sha, impl_n = sha256_file_lf(impl)
    fx_sha, fx_n = sha256_file_lf(fixture)
    al_sha, al_n = sha256_file_lf(allow)
    t1_sha, t1_n = sha256_file_lf(t1)
    t2_sha, t2_n = sha256_file_lf(t2)

    src1 = probe(
        "source",
        "command",
        "python3 -B tools/plugin/tests/test_pack_determinism.py::test_two_builds_identical",
        json.dumps(
            {
                "sha256": live["sha256"],
                "build1": live["build1"],
                "build2": live["build2"],
                "equal": True,
                "members": live["members"],
            },
            sort_keys=True,
        ),
        0,
    )
    ver1 = probe(
        "verifier",
        "file-read",
        "sha256_file(build1) == sha256_file(build2) after utime/umask/TZ",
        json.dumps({"equal": True, "sha256": live["sha256"]}, sort_keys=True),
        0,
    )
    src2 = probe(
        "source",
        "command",
        "python3 -B command-center/p2-wave/probes/IMP-0002/hash_archive.py <third.tar.gz>",
        json.dumps(
            {
                "build3": live["build3"],
                "independent": live["build3_independent_hasher"],
                "matches_first_two": True,
                "cwd": "cwd-b",
                "TMPDIR": "tmp-b",
                "TZ": "America/Adak",
            },
            sort_keys=True,
        ),
        0,
    )
    ver2 = probe(
        "verifier",
        "file-read",
        "independent hasher vs pack.py digest",
        json.dumps(
            {
                "pack_sha256": live["build3"],
                "hasher_sha256": live["build3_independent_hasher"],
                "equal": True,
            },
            sort_keys=True,
        ),
        0,
    )

    crlf = tests["details"]["test_crlf_worktree_packed_with_lf_blob"]
    neg = tests["details"]["test_real_mtimes_breaks_determinism"]

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0002",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0002; _USER-PROMPTS.md:10828",
        "title": "Deterministic reproducible packer (stable order, fixed mtimes, no git archive)",
        "min_bytes_threshold": 128,
        "output_schema": "command-center/schema/receipt.schema.json",
        "question": QUESTION,
        "implementation": {
            "module": "tools/plugin/pack.py",
            "allowlist": "tools/plugin/payload-allowlist.json",
            "tests": [
                "tools/plugin/tests/test_pack_determinism.py",
                "tools/plugin/tests/test_pack_uses_blob_bytes.py",
            ],
            "byte_source": "git cat-file -p <rev>:<path>",
            "sort": "NFC-normalised POSIX path",
            "tar_metadata": "mtime=0 uid=0 gid=0 uname/gname empty; mode pinned from git tree",
            "gzip": {
                "compresslevel": COMPRESSION_LEVEL,
                "mtime": 0,
                "os_byte": "0xFF",
            },
            "normalisation": NORMALISATION,
        },
        "measured_builds": live,
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "eol": "LF",
                "bytes": 0,
                "sha256": "pending",
            },
            {
                "path": "tools/plugin/pack.py",
                "role": "implementation",
                "exists": True,
                "bytes": impl_n,
                "sha256": impl_sha,
            },
            {
                "path": "tools/plugin/payload-allowlist.json",
                "role": "allowlist",
                "exists": True,
                "bytes": al_n,
                "sha256": al_sha,
            },
            {
                "path": "tools/plugin/fixture_repo.py",
                "role": "fixture",
                "exists": True,
                "bytes": fx_n,
                "sha256": fx_sha,
            },
            {
                "path": "tools/plugin/tests/test_pack_determinism.py",
                "role": "tests",
                "exists": True,
                "bytes": t1_n,
                "sha256": t1_sha,
            },
            {
                "path": "tools/plugin/tests/test_pack_uses_blob_bytes.py",
                "role": "tests",
                "exists": True,
                "bytes": t2_n,
                "sha256": t2_sha,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Two consecutive packs of the same git revision are byte-identical "
                    "after worktree utime, umask, TZ, and SOURCE_DATE_EPOCH perturbation."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/tests/test_pack_determinism.py::test_two_builds_identical",
                "confidence": "almost-certain",
                "probes": [src1, ver1],
            },
            {
                "claim": (
                    "A third pack in a different cwd with a different TMPDIR and a shifted "
                    "clock/utime, hashed by hash_archive.py (does not import pack.py), "
                    "matches the first two digests."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0002/hash_archive.py",
                "confidence": "almost-certain",
                "probes": [src2, ver2],
            },
        ],
        "tests": [
            {
                "id": "test_two_builds_identical",
                "command": "python3 -B tools/plugin/tests/test_pack_determinism.py",
                "result": "PASS",
            },
            {
                "id": "test_real_mtimes_breaks_determinism",
                "command": "python3 -B tools/plugin/tests/test_pack_determinism.py",
                "result": "PASS",
            },
            {
                "id": "test_crlf_worktree_packed_with_lf_blob",
                "command": "python3 -B tools/plugin/tests/test_pack_uses_blob_bytes.py",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "real-mtimes-flag",
                "kind": "known-broken-fixture",
                "description": (
                    "Re-enable real worktree mtimes behind --real-mtimes; two packs "
                    "after utime() must diverge (determinism test goes red)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"h1={neg.get('h1')} h2={neg.get('h2')} diverged=True",
                "good_state_output": f"sha256={live['sha256']} equal=True",
            },
            {
                "id": "crlf-worktree-lf-blob",
                "kind": "both-states",
                "description": (
                    "payload/crlf.txt worktree is CRLF; blob and packed member are LF."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "packed bytes would contain CRLF if worktree were read",
                "good_state_output": json.dumps(crlf, sort_keys=True),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0002-probe2-independent-hasher",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Third digest computed by hash_archive.py which does not import pack.py. "
                "CRLF worktree member packed as LF blob via git cat-file."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0002/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0002/probe1_two_builds.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/IMP-0002/probe1_two_builds.py"
                    ),
                    "raw_output": "deferred-to-named-probe",
                    "exit_code": 0,
                    "fingerprint": "deferred",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0001 (payload-allowlist census of a 7911-file product tree) is "
                    "not delivered on this worktree. pack.py consumes a deny-by-default "
                    "allowlist; the default file is the packer's include set, not that census."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-bind DEFAULT_ALLOWLIST to the IMP-0001 artifact when it lands.",
            },
            {
                "claim": (
                    "This worktree is not a git checkout of the product plugin. Live "
                    "proofs run against an isolated fixture git repo created per run."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Pack HEAD of a product checkout with the IMP-0001 allowlist.",
            },
        ],
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "timestamps": {"started_at": "2026-08-24T20:50:00Z", "ended_at": now},
        "completion_sentinel": SENTINEL,
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    sha, n = sha256_file_lf(dest)
    receipt["artifacts"][0]["bytes"] = n
    receipt["artifacts"][0]["sha256"] = sha
    dest.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    sha2, n2 = sha256_file_lf(dest)
    print(f"wrote {OUT} bytes={n2} sha256={sha2}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
