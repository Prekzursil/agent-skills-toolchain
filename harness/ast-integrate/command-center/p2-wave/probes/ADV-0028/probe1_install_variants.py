#!/usr/bin/env python3
"""Probe 1: install unsigned / truncated / old-content / untrusted-key packages.

Records accept/reject plus the exact failure mode. Live path is
tools.plugin.install.apply_install. Sidecar signatures are computed independently
so a digest-only installer cannot hide behind a missing-harness excuse.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_variant_matrix  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0028-signature-verification-bypass.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def catalog_sentinel() -> str:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "ADV-0028":
            return str(unit.get("completion_sentinel") or "")
    return ""
TARGETS = (
    "unsigned",
    "truncated_signature",
    "signature_over_older_content",
    "untrusted_key",
)


def main() -> int:
    live = run_variant_matrix()
    bypass = live["bypass"]
    attempts = live["attempts"]
    sidecars = live["sidecars"]
    print(
        json.dumps(
            {
                "probe": "probe1-install-variants",
                "unit_id": "ADV-0028",
                "bypass": bypass,
                "control_trusted_signed_installs": live["control_trusted_signed_installs"],
                "liveness_digest_mismatch_refuses": live[
                    "liveness_digest_mismatch_refuses"
                ],
                "installer_inspected_signature": live["installer_inspected_signature"],
                "signature_api_present": live["source_scan"]["signature_api_present"],
                "truncated_verifies": sidecars["truncated"]["verifies_for_payload"],
                "old_content_verifies_for_current": sidecars["old_content"][
                    "verifies_for_payload"
                ],
                "trusted_control_verifies": sidecars["trusted_signed_control"][
                    "verifies_for_payload"
                ],
                "failure_modes": {
                    name: attempts[name].get("failure_mode")
                    for name in list(TARGETS)
                    + ["trusted_signed_control", "digest_mismatch_liveness"]
                },
            },
            indent=1,
            sort_keys=True,
        )
    )
    if live["source_scan"]["signature_api_present"]:
        print("FAILED:ADV-0028-probe1 unexpected signature API in installer source")
        return 1
    if not all(bypass.values()):
        print("FAILED:ADV-0028-probe1 a malicious variant was rejected")
        return 1
    if not live["control_trusted_signed_installs"]:
        print("FAILED:ADV-0028-probe1 trusted-signed control did not install")
        return 1
    if not live["liveness_digest_mismatch_refuses"]:
        print("FAILED:ADV-0028-probe1 digest-mismatch liveness did not refuse")
        return 1
    if sidecars["truncated"]["verifies_for_payload"]:
        print("FAILED:ADV-0028-probe1 truncated sidecar unexpectedly verified")
        return 1
    if sidecars["old_content"]["verifies_for_payload"]:
        print("FAILED:ADV-0028-probe1 old-content sidecar verified for current blob")
        return 1
    if not sidecars["old_content"]["verifies_for_older_blob"]:
        print("FAILED:ADV-0028-probe1 old-content sidecar did not verify older blob")
        return 1
    if not sidecars["trusted_signed_control"]["verifies_for_payload"]:
        print("FAILED:ADV-0028-probe1 trusted control sidecar did not verify")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ADV-0028-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:ADV-0028-probe1 artifact unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:ADV-0028-probe1 self-declared {doc.get('state')}")
        return 1
    sentinel = catalog_sentinel()
    if not sentinel or sentinel not in text:
        print("FAILED:ADV-0028-probe1 sentinel absent")
        return 1
    recorded = ((doc.get("probe1") or {}).get("bypass")) or {}
    for key, val in bypass.items():
        if recorded.get(key) != val:
            print(f"FAILED:ADV-0028-probe1 artifact drift on {key}")
            return 1
    print("SUCCESS:ADV-0028-probe1 unsigned/truncated/old-content/untrusted all accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
