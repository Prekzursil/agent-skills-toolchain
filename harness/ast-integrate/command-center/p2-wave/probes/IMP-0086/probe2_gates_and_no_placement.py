#!/usr/bin/env python3
"""Named probe 2: no marketplace placement code; each failed gate aborts before handoff."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.install import marketplace_install  # noqa: E402
from marketplace.placement_audit import audit_tree  # noqa: E402
from marketplace.tests.support import (  # noqa: E402
    PACKAGE_REF,
    generate_publisher,
    good_request,
    sign_digest,
    write_deterministic_tar,
)
from marketplace.verify import (  # noqa: E402
    GATE_COMPATIBILITY,
    GATE_LOCKFILE_DIGEST,
    GATE_REVOCATION,
    GATE_SIGNATURE,
    GateFailure,
)
from plugin.census import census  # noqa: E402

INSTALL_SRC = REPO / "tools" / "marketplace" / "install.py"


class RecordingInstaller:
    def __init__(self) -> None:
        self.calls: list = []

    def install_from_handoff(self, handoff, dest_home):
        self.calls.append(True)
        raise AssertionError("handoff reached")


def _order_in_source() -> bool:
    src = INSTALL_SRC.read_text(encoding="utf-8")
    i_verify = src.find("run_verification(")
    i_deliver = src.find("deliver(")
    i_extract = src.find("extractall")
    return i_verify != -1 and i_deliver != -1 and i_verify < i_deliver and i_extract == -1


def main() -> int:
    findings = audit_tree()
    order_ok = _order_in_source()
    gate_rows = []
    with tempfile.TemporaryDirectory(prefix="imp0086-p2-") as raw:
        tmp = Path(raw)
        blob = tmp / "demo.tar.gz"
        digest = write_deterministic_tar(blob)
        private, public_hex = generate_publisher()
        signature = sign_digest(private, digest)
        cases = [
            (
                GATE_LOCKFILE_DIGEST,
                dict(
                    lockfile={
                        "resolver_version": "1",
                        "packages": {
                            PACKAGE_REF: {
                                "digest": "sha256:" + "cd" * 32,
                                "source": str(blob),
                            }
                        },
                    }
                ),
            ),
            (GATE_SIGNATURE, dict(signature=None)),
            (
                GATE_REVOCATION,
                dict(revocation={"revoked_versions": [PACKAGE_REF], "revoked_keys": []}),
            ),
            (
                GATE_COMPATIBILITY,
                dict(compatibility={"platforms": ["win32"], "client_min": "0.1.0"}),
            ),
        ]
        for gate, overrides in cases:
            dest = tmp / f"home-{gate}"
            recorder = RecordingInstaller()
            sig = overrides.pop("signature", signature)
            req = good_request(
                dest,
                tmp / f"cache-{gate}",
                blob,
                digest,
                sig,
                public_hex,
                installer=recorder,
                **overrides,
            )
            caught: str | None = None
            try:
                marketplace_install(req)
            except GateFailure as exc:
                caught = exc.gate
            gate_rows.append(
                {
                    "gate": gate,
                    "caught": caught,
                    "handoff_calls": len(recorder.calls),
                    "dest_census": sorted(census(dest)),
                    "aborted_before_handoff": caught == gate
                    and not recorder.calls
                    and not census(dest),
                }
            )

    payload = {
        "probe": "probe2-gates-and-no-placement",
        "unit_id": "IMP-0086",
        "placement_findings": findings,
        "verify_before_deliver_in_source": order_ok,
        "gates": gate_rows,
        "pass": bool(
            not findings
            and order_ok
            and gate_rows
            and all(r["aborted_before_handoff"] for r in gate_rows)
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0086-probe2 placement audit or gate abort")
        return 1
    print("SUCCESS:IMP-0086-probe2 no marketplace placement; gates abort before handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
