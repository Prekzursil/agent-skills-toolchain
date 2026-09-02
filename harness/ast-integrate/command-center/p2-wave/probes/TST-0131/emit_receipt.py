#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0131.json from a live truncation run.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from harness import (  # noqa: E402
    PACKAGE_ID,
    TRUNCATE_AFTER,
    fixture_blob,
    full_url,
    listing_names_package,
    quarantine_is_outside_cache,
    serve_blob,
    truncate_url,
)
from package_download import (  # noqa: E402
    REASON_DIGEST_MISMATCH,
    download_package,
    independent_cache_listing,
    install_from_cache,
    naive_write_partial_into_cache,
    sha256_hex,
)

OUT = "command-center/receipts/TST-0131.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0131"
QUESTION = (
    "When a package download is reset after N of M bytes, is the partial file "
    "quarantined outside the cache and the integrity failure reported by digest "
    "mismatch? PASS requires: the cache contains no entry for that package "
    "afterward, and a later successful install is not poisoned by the truncated remnant."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0131/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0131/probe2_follow_on.py"
)
IMPL = "tools/marketplace/package_download.py"
TESTS = "tools/marketplace/tests/test_package_download.py"
SEED = 131


def sha_file(rel: str) -> tuple[int, str, bool]:
    path = REPO / rel
    if not path.is_file():
        return 0, "", False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return len(raw), hashlib.sha256(raw).hexdigest(), True


def run_cmd(cmd: str, timeout: int = 120) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    size, digest, exists = sha_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": exists,
        "role": role,
    }


def measure() -> dict:
    blob = fixture_blob()
    expected = sha256_hex(blob)
    n = TRUNCATE_AFTER
    m = len(blob)
    with tempfile.TemporaryDirectory(prefix="tst0131-emit-") as tmp:
        tmp_path = Path(tmp)
        cache = tmp_path / "cache"
        quarantine = tmp_path / "quarantine"
        install = tmp_path / "install"
        cache_trunc = tmp_path / "cache-trunc"
        q_trunc = tmp_path / "q-trunc"
        naive_cache = tmp_path / "naive"
        naive_install = tmp_path / "naive-install"
        with serve_blob(blob) as base:
            good = download_package(
                full_url(base),
                PACKAGE_ID,
                expected,
                cache,
                quarantine,
                install_root=install,
            )
            trunc = download_package(
                truncate_url(base, n),
                PACKAGE_ID,
                expected,
                cache_trunc,
                q_trunc,
            )
            listing = independent_cache_listing(cache_trunc, PACKAGE_ID)
            follow = download_package(
                full_url(base),
                PACKAGE_ID,
                expected,
                cache_trunc,
                q_trunc,
                install_root=install / "follow",
            )
            naive_path = naive_write_partial_into_cache(
                truncate_url(base, n), PACKAGE_ID, naive_cache
            )
            naive_hits = independent_cache_listing(naive_cache, PACKAGE_ID)
            poisoned = install_from_cache(naive_cache, PACKAGE_ID, naive_install)
            qpath = Path(trunc.quarantine_path or "")
            follow_path = Path(follow.installed_path or "")
            follow_bytes = follow_path.read_bytes() if follow_path.is_file() else b""
            return {
                "n": n,
                "m": m,
                "package_id": PACKAGE_ID,
                "expected_digest": expected,
                "truncated_digest": trunc.received_digest,
                "good": good.to_dict(),
                "trunc": trunc.to_dict(),
                "follow": follow.to_dict(),
                "independent_listing_after_trunc": listing,
                "listing_empty": listing == [],
                "quarantine_outside_cache": bool(qpath.is_file())
                and quarantine_is_outside_cache(qpath, cache_trunc),
                "follow_digest": sha256_hex(follow_bytes) if follow_bytes else "",
                "follow_matches_full": bool(follow_bytes)
                and sha256_hex(follow_bytes) == expected,
                "follow_not_remnant": bool(follow_bytes)
                and sha256_hex(follow_bytes) != trunc.received_digest,
                "naive_size": naive_path.stat().st_size,
                "naive_listing_sees_package": listing_names_package(
                    naive_hits, PACKAGE_ID
                ),
                "naive_poisoned_digest": sha256_hex(poisoned.read_bytes()),
                "naive_poisoned": sha256_hex(poisoned.read_bytes())
                == trunc.received_digest,
            }


def main() -> int:
    measured = measure()
    if not measured["good"]["ok"]:
        print("FAILED:TST-0131 emit complete-download control")
        print(json.dumps(measured["good"], indent=2))
        return 1
    trunc = measured["trunc"]
    if (
        trunc["ok"]
        or trunc["classification"] != REASON_DIGEST_MISMATCH
        or "digest-mismatch" not in trunc["message"]
        or trunc["received_bytes"] != measured["n"]
        or not measured["listing_empty"]
        or not measured["quarantine_outside_cache"]
    ):
        print("FAILED:TST-0131 emit truncation quarantine")
        print(json.dumps(measured, indent=2, default=str)[:4000])
        return 1
    if not measured["follow"]["ok"] or not measured["follow_matches_full"]:
        print("FAILED:TST-0131 emit follow-on poisoned or failed")
        return 1
    if not measured["naive_poisoned"] or not measured["naive_listing_sees_package"]:
        print("FAILED:TST-0131 emit naive control did not fire")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0131 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    test_code, test_text = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B " + TESTS, timeout=120
    )
    if test_code != 0:
        print(test_text[-4000:])
        print("FAILED:TST-0131 emit unit tests")
        return 1

    supporting = [
        IMPL,
        TESTS,
        SCHEMA,
        "command-center/p2-wave/probes/TST-0131/harness.py",
        "command-center/p2-wave/probes/TST-0131/probe1_both_states.py",
        "command-center/p2-wave/probes/TST-0131/probe2_follow_on.py",
        "command-center/p2-wave/probes/TST-0131/emit_receipt.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print("FAILED:TST-0131 missing supporting", missing)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl_b, impl_s, _ = sha_file(IMPL)
    receipt = {
        "unit_id": "TST-0131",
        "id": "TST-0131",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "title": "Mid-stream truncation of a package download is quarantined",
        "report_kind": "fault-injection-receipt",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "seed": SEED,
        "scratch_only": True,
        "host_clock_mutated": False,
        "min_bytes_threshold": 256,
        "b07_note": (
            "Live Program-B B07 registry + package-download client is absent "
            "from this sparse worktree (tools/lib/net-allowlist.mjs also absent). "
            "tools/marketplace/package_download.py is the bound loopback client: "
            "HTTP GET, digest check before cache promotion, partials quarantined "
            "outside cache. Fixture registry is 127.0.0.1 only."
        ),
        "implementation": {
            "downloader": {
                "path": IMPL,
                "bytes": impl_b,
                "sha256": impl_s,
            },
            "package_id": measured["package_id"],
            "n": measured["n"],
            "m": measured["m"],
        },
        "primitives": [
            {
                "id": "net.truncated_response",
                "family": "network",
                "shipped": True,
                "reversible": True,
                "declared_fault": "Content-Length=M then close after N bytes",
            },
            {
                "id": "net.midstream_disconnect",
                "family": "network",
                "shipped": True,
                "reversible": True,
                "declared_fault": "socket shutdown after N of M payload bytes",
            },
            {
                "id": "fs.quarantine_partial",
                "family": "filesystem",
                "shipped": True,
                "reversible": True,
                "declared_fault": "partial payload written only under quarantine_root",
            },
            {
                "id": "fs.cache_isolation",
                "family": "filesystem",
                "shipped": True,
                "reversible": True,
                "declared_fault": "failed fetch never creates cache/<package_id>",
            },
        ],
        "evidence": [
            {
                "anchor": f"{IMPL}:download_package",
                "claim": (
                    "Truncation after N of M bytes emits classification "
                    "digest-mismatch from the downloader (received sha256 != "
                    "registry digest); message names digest-mismatch."
                ),
                "verdict": "CONFIRMED",
                "classification": trunc["classification"],
                "message": trunc["message"],
                "received_bytes": trunc["received_bytes"],
                "claimed_bytes": trunc["claimed_bytes"],
                "expected_digest": measured["expected_digest"],
                "received_digest": measured["truncated_digest"],
            },
            {
                "anchor": f"{IMPL}:independent_cache_listing",
                "claim": (
                    "Independent os.walk of the cache after truncation shows "
                    "zero entries for the package id; the partial lives in "
                    "quarantine, not cache."
                ),
                "verdict": "CONFIRMED",
                "listing": measured["independent_listing_after_trunc"],
                "listing_empty": measured["listing_empty"],
                "quarantine_outside_cache": measured["quarantine_outside_cache"],
            },
        ],
        "tests": [
            {
                "id": "both-states-complete-download-installs-cleanly",
                "result": "PASS",
                "digest": measured["expected_digest"],
            },
            {
                "id": "truncation-emits-digest-mismatch-cache-empty",
                "result": "PASS",
                "classification": REASON_DIGEST_MISMATCH,
            },
            {
                "id": "follow-on-install-after-truncation-correct-digest",
                "result": "PASS",
                "follow_digest": measured["follow_digest"],
                "not_remnant": measured["follow_not_remnant"],
            },
            {
                "id": "naive-write-into-cache-poisons-follow-on",
                "result": "PASS",
                "detector_control": True,
                "naive_poisoned": measured["naive_poisoned"],
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-states-truncation-quarantine",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "follow-on-install-not-poisoned",
                "raw_output": t2,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0131-probe2-follow-on-independent-listing",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 is a separate process: new temp roots, new fixture "
                "server. It re-lists the cache with os.walk and compares the "
                "follow-on digest to both the full fixture and the remnant."
            ),
        },
        "artifacts": artifacts
        + [
            {
                "path": OUT,
                "role": "primary",
                "note": "this receipt; sha256 filled by write_receipts.py after write",
            }
        ],
        "measured": {
            "n": measured["n"],
            "m": measured["m"],
            "package_id": measured["package_id"],
            "expected_digest": measured["expected_digest"],
            "truncated_digest": measured["truncated_digest"],
            "listing_after_trunc": measured["independent_listing_after_trunc"],
            "follow_digest": measured["follow_digest"],
            "naive_poisoned": measured["naive_poisoned"],
            "unit_test_tail": test_text[-1500:],
        },
        "negative_controls": {
            "naive_write_into_cache_visible_to_listing": measured[
                "naive_listing_sees_package"
            ],
            "naive_follow_on_installs_remnant_digest": measured["naive_poisoned"],
        },
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "notes": (
            "G-1 for TST-0131: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild. Scratch-only fixture "
            "on 127.0.0.1; host clock was not set. SUCCESS:TST-0131"
        ),
        "ts": now,
        "cloud_ok": False,
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(receipt, indent=1, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
