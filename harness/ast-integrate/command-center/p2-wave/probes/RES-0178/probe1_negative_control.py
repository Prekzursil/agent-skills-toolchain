#!/usr/bin/env python3
"""Probe 1: listed package fails the auto-install bar; fabricated name must not count."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lineage as L  # noqa: E402
import minbar as M  # noqa: E402

ART = L.REPO / L.ARTIFACT_REL
FABRICATED = "acme/totally-safe-signed-mcp"
TOKEN = "tumf/mcp-shell-server"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0178-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:RES-0178" not in text:
        print("FAILED:RES-0178-probe1 sentinel absent")
        return 1

    awesome = L.assert_snippet("awesome-mcp-servers-readme", TOKEN)
    pkg = L.assert_snippet("tumf-mcp-shell-server-readme", "ALLOW_COMMANDS")
    if FABRICATED in awesome["text"]:
        print("FAILED:RES-0178-probe1 fabricated token unexpectedly listed")
        return 1

    model = M.package_from_captures(
        listing_text=awesome["text"],
        listing_token=TOKEN,
        package_text=pkg["text"],
        shell_markers=("whitelisted shell commands", "ALLOW_COMMANDS"),
        provenance_markers=("sigstore", "npm provenance", "in-toto"),
        review_record_markers=(
            "security review of tumf/mcp-shell-server",
            "audit report for tumf/mcp-shell-server",
        ),
        digest_in_listing=False,
    )
    live = M.evaluate(model)
    print(f"listed={TOKEN} bar_pass={live['pass']} reasons={live['fail_reasons']}")
    if live["pass"]:
        print("FAILED:RES-0178-probe1 listed shell package unexpectedly met the bar")
        return 1
    need = {
        "missing-artifact-provenance",
        "missing-pinned-digest",
        "excessive-capability",
        "review-not-observed-for-this-version",
        "revocation-metadata-only",
    }
    if not need.issubset(set(live["fail_reasons"])):
        print(f"FAILED:RES-0178-probe1 missing fail reasons {need - set(live['fail_reasons'])}")
        return 1

    # Sampled-listing rows live under sampled_listing_controls since the
    # receipt-core schema reserved negative_controls for envelope-format
    # control rows (id/kind/fired_on_bad_state/...). Same rows, same checks.
    controls = doc.get("sampled_listing_controls") or doc.get("negative_controls") or []
    if not controls:
        print("FAILED:RES-0178-probe1 empty sampled_listing_controls (unsampled survey)")
        return 1
    hit = False
    for row in controls:
        if row.get("package") != TOKEN:
            continue
        hit = True
        if row.get("fails_auto_install_bar") is not True:
            print("FAILED:RES-0178-probe1 artifact did not mark listing as failing")
            return 1
        claimed = set(row.get("fail_reasons") or [])
        if claimed != set(live["fail_reasons"]):
            print(
                f"FAILED:RES-0178-probe1 fail_reasons drift claimed={claimed} live={live['fail_reasons']}"
            )
            return 1
    if not hit:
        print("FAILED:RES-0178-probe1 artifact omitted the listed failing package")
        return 1

    fab = doc.get("fabricated_control") or {}
    if fab.get("package") != FABRICATED:
        print("FAILED:RES-0178-probe1 fabricated_control missing")
        return 1
    if (doc.get("auto_install_bar") or {}).get("any_sampled_listing_meets_bar") is not False:
        print("FAILED:RES-0178-probe1 auto_install_bar falsely green")
        return 1

    print("fabricated_absent=True detector_control=True")
    print("SUCCESS:RES-0178-probe1 negative control recomputed from captures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
