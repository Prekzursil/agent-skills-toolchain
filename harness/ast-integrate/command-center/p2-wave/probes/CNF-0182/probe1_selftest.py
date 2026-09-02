#!/usr/bin/env python3
"""Probe 1: re-run every package, secret-scan, portability, census non-empty."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
import executil  # noqa: E402
import guards  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0182-probe1 {msg}")
    return 1


def main() -> int:
    receipt = C.REPO / C.OUT_REL
    if not receipt.is_file():
        return fail("receipt missing")
    doc = C.load_json(receipt)
    if "SUCCESS:CNF-0182" not in receipt.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    packages = C.domain(doc, "packages") or []
    if len(packages) < 1:
        return fail("empty packages")
    census = C.domain(doc, "census") or {}
    if int(census.get("claim_count") or 0) != len(packages):
        return fail("census.claim_count != packages")
    runs = {
        r["package_id"]: r
        for r in (C.domain(doc, "authoring_runs") or [])
        if isinstance(r, dict)
    }
    for pkg in packages:
        pid = pkg["package_id"]
        recorded = runs.get(pid) or {}
        if recorded.get("exit_code") != 0:
            return fail(f"authoring {pid} not green")
        rc, tail = executil.run_cmd(pkg["one_command"])
        print(f"rerun {pid} rc={rc}")
        if rc != 0:
            print(tail[-1500:])
            return fail(f"rerun {pid} rc={rc}")
    secret_hits = guards.scan_tree(C.PACKAGES)
    port_hits = guards.portability_hits(C.PACKAGES)
    print(f"secret_hits={len(secret_hits)} port_hits={len(port_hits)}")
    if secret_hits:
        return fail(f"secret scan {secret_hits}")
    if port_hits:
        return fail(f"portability {port_hits}")
    creds = C.domain(doc, "credentials_policy") or {}
    if creds.get("bundled") is not False:
        return fail("credentials bundled")
    print(f"packages={len(packages)} census_source={census.get('source')}")
    print("SUCCESS:CNF-0182-probe1 self-test secret-scan portability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
