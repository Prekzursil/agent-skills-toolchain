#!/usr/bin/env python3
"""Probe 1: a revoked package is refused at install; a non-revoked package installs.

Filesystem census is the second instrument (independent of the Decision object):
refused installs place zero payload files; the negative-control install places one.
Also refuses a package whose publisher key is on the list.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    COMPROMISED,
    EVIL,
    SAFE,
    census_payloads,
    install,
    make_client,
    serve_signed,
)
from tools.marketplace.revocation_list.fixtures.harness import StaticTransport  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0079-p1-") as tmp:
        root = Path(tmp)
        dest = root / "dest"
        transport = StaticTransport()
        client, sink, _clock = make_client(root, transport)
        serve_signed(transport)

        evil = install(client, EVIL, dest)
        compromised = install(client, COMPROMISED, dest)
        safe = install(client, SAFE, dest)
        files = census_payloads(dest)

        report = {
            "probe": "probe1-revoked-refused",
            "unit_id": "IMP-0079",
            "evil_placed": evil.placed,
            "evil_action": evil.decision.action,
            "evil_reason": evil.decision.reason,
            "compromised_placed": compromised.placed,
            "compromised_action": compromised.decision.action,
            "safe_placed": safe.placed,
            "safe_bytes": safe.placed_bytes,
            "census": files,
            "negative_control_installs": safe.placed and files == ["pkg.safe/1.0.0/payload.bin"],
        }
        print(json.dumps(report, indent=1))

        if evil.placed or compromised.placed:
            print("FAILED:IMP-0079-probe1 revoked install placed files")
            return 1
        if evil.decision.action != "REFUSE" or compromised.decision.action != "REFUSE":
            print("FAILED:IMP-0079-probe1 expected REFUSE")
            return 1
        if not safe.placed:
            print("FAILED:IMP-0079-probe1 negative control did not install")
            return 1
        if files != ["pkg.safe/1.0.0/payload.bin"]:
            print(f"FAILED:IMP-0079-probe1 census={files}")
            return 1
        payload = dest / "pkg.safe/1.0.0/payload.bin"
        if payload.read_bytes() != b"safe-payload":
            print("FAILED:IMP-0079-probe1 payload mismatch")
            return 1

    print(
        "revoked_version_refused=True revoked_key_refused=True "
        "negative_control_installed=True census_only_safe=True"
    )
    print("SUCCESS:IMP-0079-probe1 revoked package refused; non-revoked installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
