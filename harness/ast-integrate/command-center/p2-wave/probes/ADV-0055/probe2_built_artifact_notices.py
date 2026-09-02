#!/usr/bin/env python3
"""Probe 2: notice check on the built artifact, not the source tree.

Mechanically different from probe 1 (archive member/content scan vs lockfile
walk). Both-states: packed OpenSSL binding with notices is SILENT; the same
payload without notices FIRES. A decoy NOTICE in the source fixtures must
not green the missing-notice archive.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import notices as N  # noqa: E402

sys.path.insert(0, str(REPO / "tools"))
from plugin.pack import pack_staging  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0055-probe2 {msg}")
    return 1


def pack_live_tooling(tmpdir: Path) -> Path:
    """Pack live signing/packaging sources with the live packer (pack_staging)."""
    staging = tmpdir / "live-staging"
    files = [
        "tools/plugin/pack.py",
        "tools/plugin/payload.py",
        "tools/marketplace/blob_store.py",
        "tools/plugin/census.py",
        "tools/plugin/healthcheck.py",
    ]
    names: list[str] = []
    for rel in files:
        src = REPO / rel
        if not src.is_file():
            raise RuntimeError(f"live tooling missing {rel}")
        dest = staging / Path(rel).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        names.append(Path(rel).name)
    manifest = tmpdir / "live-manifest.json"
    manifest.write_text(json.dumps({"files": names}), encoding="utf-8")
    out = tmpdir / "live-packaging-tooling.zip"
    rc = pack_staging(staging, manifest, out)
    if rc != 0 or not out.is_file():
        raise RuntimeError(f"plugin.pack pack_staging failed rc={rc}")
    return out


def main() -> int:
    good = N.inspect_archive(N.build_zip(N.payload_with_notices()), "zip")
    bad = N.inspect_archive(N.build_zip(N.payload_without_notices()), "zip")
    plat = N.inspect_archive(N.build_zip(N.payload_platform_hash_only()), "zip")
    rev_good = N.reviewer_from_names(good["members"], good["has_bundled_crypto"])
    rev_bad = N.reviewer_from_names(bad["members"], bad["has_bundled_crypto"])

    decoy = HERE / "fixtures" / "SOURCE-DECOY-NOTICE.txt"
    decoy_text = decoy.read_text(encoding="utf-8") if decoy.is_file() else ""
    decoy_in_source = N.DECOY_CANARY in decoy_text

    with tempfile.TemporaryDirectory(prefix="adv0055-") as raw:
        tmp = Path(raw)
        live_zip = pack_live_tooling(tmp)
        live = N.inspect_path(live_zip)

    report = {
        "probe": "probe2-built-artifact-notices",
        "unit_id": "ADV-0055",
        "mechanism": "zip-member-and-content-scan-not-source-grep",
        "observation_method": (
            "zipfile.ZipFile namelist+read of packed bytes. "
            "Live archive emitted by tools.plugin.pack.pack_staging (the packaging tool). "
            "Source-tree decoy NOTICE is not opened."
        ),
        "with_notices": {
            "status": good["status"],
            "bundled": good["bundled_crypto_members"],
            "missing": good["missing_notices"],
            "openssl_attribution": good["openssl_attribution"],
            "export_classification": good["export_classification"],
            "reviewer": rev_good,
        },
        "without_notices": {
            "status": bad["status"],
            "bundled": bad["bundled_crypto_members"],
            "missing": bad["missing_notices"],
            "openssl_attribution": bad["openssl_attribution"],
            "export_classification": bad["export_classification"],
            "decoy_canary": bad["decoy_canary"],
            "reviewer": rev_bad,
        },
        "platform_hash_only": {
            "status": plat["status"],
            "bundled": plat["bundled_crypto_members"],
            "required": plat["required_notices"],
        },
        "live_built_packaging_tooling": {
            "status": live["status"],
            "member_count": live["member_count"],
            "members": live["members"],
            "bundled": live["bundled_crypto_members"],
            "required": live["required_notices"],
            "missing": live["missing_notices"],
            "decoy_canary": live["decoy_canary"],
            "packer": "tools.plugin.pack.pack_staging",
        },
        "source_decoy_present_on_disk": decoy_in_source,
    }
    print(json.dumps(report, sort_keys=True))

    if good["status"] != "SILENT":
        return fail(f"with-notices archive fired: {good['missing_notices']}")
    if not good["openssl_attribution"] or not good["export_classification"]:
        return fail("with-notices archive missing content matches")
    if bad["status"] != "FIRE":
        return fail("without-notices archive was SILENT; detector cannot go red")
    if bad["decoy_canary"]:
        return fail("without-notices archive contains source decoy; scan leaked")
    if not decoy_in_source:
        return fail("source decoy fixture missing")
    if plat["status"] != "SILENT" or plat["has_bundled_crypto"]:
        return fail("platform-hash-only archive treated as bundled crypto")
    if live["has_bundled_crypto"]:
        return fail(f"live packed tooling contains bundled crypto members: {live['bundled_crypto_members']}")
    if live["decoy_canary"]:
        return fail("live packed tooling picked up source decoy")
    if live["status"] != "SILENT":
        return fail("live packed tooling FIRE with no bundled crypto")
    if rev_good["status"] != "SILENT" or rev_bad["status"] != "FIRE":
        return fail("reviewer basename scan disagreed with content scan")
    if set(live["members"]) == set():
        return fail("live packed tooling zip empty")

    print(
        "BOTH-STATES with-notices=SILENT without-notices=FIRE "
        f"missing={bad['missing_notices']}"
    )
    print(
        "NEGATIVE-CONTROL verbatim: on the packed cryptography/_openssl.so "
        "archive WITHOUT NOTICE/EXPORT-CONTROL the check returns FIRE; on the "
        "same payload WITH OpenSSL attribution and ECCN text it returns SILENT; "
        "on the source-tree decoy NOTICE the without-notices archive still FIRE."
    )
    print(
        "LIVE packed by tools.plugin.pack members="
        f"{live['members']} bundled={live['bundled_crypto_members']} status={live['status']}"
    )
    print("SUCCESS:ADV-0055-probe2 built-artifact-notices both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
