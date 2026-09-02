#!/usr/bin/env python3
"""Probe 1: static scan + named missing-env error (IMP-0061 signal 1)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.plugin.credential_boundary import (  # noqa: E402
    REQUIRED_ENV,
    CredentialEnvMissing,
    MISSING_CODE_PREFIX,
    load_injected_env,
)
from tools.plugin.scan_credential_reads import scan_production  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0061.json"


def main() -> int:
    findings = scan_production(REPO)
    print(json.dumps({"static_findings": findings, "count": len(findings)}, sort_keys=True))
    if findings:
        print("FAILED:IMP-0061-probe1 static scan found credential-store reads")
        return 1

    try:
        load_injected_env({})
        print("FAILED:IMP-0061-probe1 empty env did not raise")
        return 1
    except CredentialEnvMissing as exc:
        if not exc.code.startswith(MISSING_CODE_PREFIX + ":"):
            print(f"FAILED:IMP-0061-probe1 unnamed error {exc!r}")
            return 1
        print(f"missing_env_code={exc.code}")

    env = {k: v for k, v in os.environ.items() if k not in REQUIRED_ENV}
    proc = subprocess.run(
        [sys.executable, "-B", str(REPO / "tools/plugin/cli.py"), "startup"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
        timeout=30,
    )
    print(f"cli_missing_rc={proc.returncode} stderr={proc.stderr.strip()!r}")
    if proc.returncode != 2:
        print("FAILED:IMP-0061-probe1 missing env did not exit 2")
        return 1
    if MISSING_CODE_PREFIX not in proc.stderr:
        print("FAILED:IMP-0061-probe1 missing env stderr not named")
        return 1
    if "PLUGIN_INJECTED_TOKEN" not in proc.stderr:
        print("FAILED:IMP-0061-probe1 missing env did not name PLUGIN_INJECTED_TOKEN")
        return 1

    if not ART.is_file():
        print("FAILED:IMP-0061-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0061-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0061" not in text:
        print("FAILED:IMP-0061-probe1 sentinel absent")
        return 1
    static = (doc.get("signals") or {}).get("static_scan") or {}
    if static.get("finding_count") != 0:
        print("FAILED:IMP-0061-probe1 receipt static finding_count not 0")
        return 1
    print("SUCCESS:IMP-0061-probe1 static scan clean; missing env named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
