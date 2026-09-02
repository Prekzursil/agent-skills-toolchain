#!/usr/bin/env python3
"""Probe 2: runtime file-access trace + both-states negative control (IMP-0061 signal 2)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.plugin.trace_file_access import (  # noqa: E402
    SYNTHETIC_ENV,
    scan_deliberate_literal,
    trace_command_surface,
    trace_deliberate_credential_read,
)

ART = REPO / "command-center/receipts/IMP-0061.json"
ROTATION_NEEDLES = (
    "rotate_credential",
    "revoke_credential",
    "os.unsetenv",
    "CryptProtectData",
)
SRC_FILES = (
    "tools/plugin/cli.py",
    "tools/plugin/command_surface.py",
    "tools/plugin/credential_boundary.py",
    "tools/lib/security.mjs",
    "tools/plugin/cli.mjs",
)


def main() -> int:
    good = trace_command_surface(REPO)
    print(
        json.dumps(
            {
                "commands": good["commands"],
                "credential_hits": good["credential_hits"],
                "secret_leaked_paths": good["secret_leaked_paths"],
                "opened_count": len(good["opened"]),
            },
            sort_keys=True,
        )
    )
    if good["credential_hits"]:
        print("FAILED:IMP-0061-probe2 production trace opened a credential store")
        return 1
    if good["secret_leaked_paths"]:
        print("FAILED:IMP-0061-probe2 synthetic token leaked into artifacts")
        return 1

    static_mutant = scan_deliberate_literal(REPO)
    runtime_mutant = trace_deliberate_credential_read(REPO)
    print(
        json.dumps(
            {
                "static_mutant_detected": static_mutant["detected"],
                "runtime_mutant_detected": runtime_mutant["detected"],
                "static_findings": static_mutant["findings"],
                "runtime_hits": runtime_mutant["credential_hits"],
            },
            sort_keys=True,
            default=str,
        )
    )
    if not static_mutant["detected"]:
        print("FAILED:IMP-0061-probe2 static scan missed deliberate auth.json read")
        return 1
    if not runtime_mutant["detected"]:
        print("FAILED:IMP-0061-probe2 runtime trace missed deliberate auth.json read")
        return 1

    for rel in SRC_FILES:
        text = (REPO / rel).read_text(encoding="utf-8")
        for needle in ROTATION_NEEDLES:
            if needle in text:
                print(f"FAILED:IMP-0061-probe2 rotation/revocation API {needle} in {rel}")
                return 1
        if SYNTHETIC_ENV["PLUGIN_INJECTED_TOKEN"] in text:
            print(f"FAILED:IMP-0061-probe2 synthetic token embedded in {rel}")
            return 1

    work = Path(tempfile.mkdtemp(prefix="imp0061-js-"))
    env = {**os.environ, **SYNTHETIC_ENV}
    js = subprocess.run(
        ["node", str(REPO / "tools/plugin/cli.mjs"), "status", "--root", str(work)],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
        timeout=30,
    )
    print(f"js_cli_rc={js.returncode} out={js.stdout.strip()[:200]!r}")
    if js.returncode != 0:
        print("FAILED:IMP-0061-probe2 js command surface failed")
        print(js.stderr)
        return 1
    for path in work.rglob("*"):
        if path.is_file() and SYNTHETIC_ENV["PLUGIN_INJECTED_TOKEN"] in path.read_text(
            encoding="utf-8"
        ):
            print(f"FAILED:IMP-0061-probe2 js leaked token into {path}")
            return 1

    if not ART.is_file():
        print("FAILED:IMP-0061-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0061-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0061" not in text:
        print("FAILED:IMP-0061-probe2 sentinel absent")
        return 1
    runtime = (doc.get("signals") or {}).get("runtime_trace") or {}
    if runtime.get("credential_hits"):
        print("FAILED:IMP-0061-probe2 receipt reports credential hits")
        return 1
    neg = doc.get("negative_control") or {}
    if not (neg.get("static_detected") and neg.get("runtime_detected")):
        print("FAILED:IMP-0061-probe2 receipt negative control not both-states")
        return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        print("FAILED:IMP-0061-probe2 reviewer not PASS")
        return 1
    if reviewer.get("rotation_revocation_modification") is not False:
        print("FAILED:IMP-0061-probe2 reviewer did not confirm read-only diagnosis")
        return 1
    print("SUCCESS:IMP-0061-probe2 runtime trace clean; both detectors fire on mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
