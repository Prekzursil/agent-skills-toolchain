#!/usr/bin/env python3
"""Probe 1: live Linux-container clean install from the published artifact only."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import container as C  # noqa: E402
import publish as P  # noqa: E402


def main() -> int:
    info = P.build()
    print(f"published {info['rel']} sha256={info['sha256']} bytes={info['bytes']}")
    ctr = C.run(info["path"])
    listing = ctr.get("root_listing") or []
    pre = ctr.get("artifact_listing_pre_install") or []
    markers = ctr.get("repo_markers_found") or []
    print(f"runtime={ctr.get('runtime')} digest={ctr.get('image_digest')}")
    print(f"root_listing={listing}")
    print(f"artifact_listing_pre={pre}")
    print(f"repo_checkout_present={ctr.get('repo_checkout_present')} markers={markers}")
    print(f"install_success={ctr.get('install_success')} rc={ctr.get('install_exit_code')}")
    print(f"healthy={ctr.get('healthy')} rc={ctr.get('health_exit_code')}")
    for line in (ctr.get("install_transcript") or [])[-6:]:
        print(f"install:{line}")
    for line in (ctr.get("health_output") or [])[-6:]:
        print(f"health:{line}")
    if "opt" in listing or ".git" in listing or "command-center" in listing:
        print("FAILED:CNF-0097-probe1 repo-like name in container root listing")
        return 1
    if ctr.get("repo_checkout_present") or markers:
        print("FAILED:CNF-0097-probe1 repository checkout was visible in the container")
        return 1
    if not pre or info["path"].name not in pre:
        print("FAILED:CNF-0097-probe1 pre-install listing does not show the artifact-only payload")
        return 1
    extra_pre = [n for n in pre if n not in {info["path"].name}]
    if extra_pre:
        print(f"FAILED:CNF-0097-probe1 pre-install listing had extra entries {extra_pre}")
        return 1
    if not ctr.get("install_success"):
        print("FAILED:CNF-0097-probe1 install failed")
        return 1
    if not ctr.get("healthy"):
        print("FAILED:CNF-0097-probe1 health check failed")
        return 1
    copied = ctr.get("copied_files") or []
    if "plugin.json" not in copied:
        print("FAILED:CNF-0097-probe1 plugin.json was not copied")
        return 1
    print("SUCCESS:CNF-0097-probe1 clean-install container no-repo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
