#!/usr/bin/env python3
"""stix_export: build a STIX 2.1 bundle skeleton from IOCs — offline.

Borrowed *technique* only: a minimal, deterministic STIX 2.1 exporter (indicator
SDOs for network/file IOCs, a vulnerability SDO per CVE), not a threat-platform
client. Stdlib only, no network.

Object IDs are derived with ``uuid5`` over ``type:value`` so the same IOC always
produces the same STIX id (stable diffs, no random churn); timestamps do not
affect the id. Feed it text (it will reuse ``ioc_defang.extract_iocs``) or a
pre-extracted IOC dict.

Usage:
    python3 stix_export.py "beacon to bad[.]example[.]com CVE-2021-44228"
    echo "report body" | python3 stix_export.py --created 2023-05-01T00:00:00.000Z
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone

# Stable namespace for deterministic STIX ids produced by this skill.
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://agents/skills/cti-lookup")

# IOC type -> STIX object-path used inside the pattern.
_PATTERN_PATHS = {
    "ipv4": "ipv4-addr:value",
    "ipv6": "ipv6-addr:value",
    "domain": "domain-name:value",
    "url": "url:value",
    "email": "email-addr:value",
    "md5": "file:hashes.'MD5'",
    "sha1": "file:hashes.'SHA-1'",
    "sha256": "file:hashes.'SHA-256'",
}

# Order in which indicator SDOs are emitted into a bundle (deterministic).
_INDICATOR_ORDER = ("ipv4", "ipv6", "domain", "url", "email", "md5", "sha1", "sha256")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def stix_pattern(ioc_type: str, value: str) -> str:
    """Return the STIX 2.1 comparison pattern for a single IOC."""
    path = _PATTERN_PATHS.get(ioc_type)
    if path is None:
        raise ValueError(f"no STIX pattern for IOC type {ioc_type!r}")
    return f"[{path} = '{_escape(value)}']"


def make_indicator(
    ioc_type: str, value: str, created: str, name: str | None = None
) -> dict:
    """Build a STIX 2.1 indicator SDO for one IOC (deterministic id)."""
    oid = "indicator--" + str(uuid.uuid5(NAMESPACE, f"{ioc_type}:{value}"))
    return {
        "type": "indicator",
        "spec_version": "2.1",
        "id": oid,
        "created": created,
        "modified": created,
        "name": name or f"{ioc_type} indicator: {value}",
        "indicator_types": ["malicious-activity"],
        "pattern": stix_pattern(ioc_type, value),
        "pattern_type": "stix",
        "pattern_version": "2.1",
        "valid_from": created,
    }


def make_vulnerability(cve: str, created: str) -> dict:
    """Build a STIX 2.1 vulnerability SDO for one CVE (deterministic id)."""
    oid = "vulnerability--" + str(uuid.uuid5(NAMESPACE, f"cve:{cve}"))
    return {
        "type": "vulnerability",
        "spec_version": "2.1",
        "id": oid,
        "created": created,
        "modified": created,
        "name": cve,
        "external_references": [{"source_name": "cve", "external_id": cve}],
    }


def build_bundle(iocs: dict[str, list[str]], created: str | None = None) -> dict:
    """Assemble a STIX 2.1 bundle from an IOC dict (see ioc_defang.extract_iocs)."""
    ts = created or _now_iso()
    objects: list[dict] = []
    for ioc_type in _INDICATOR_ORDER:
        for value in sorted(iocs.get(ioc_type, [])):
            objects.append(make_indicator(ioc_type, value, ts))
    for cve in sorted(iocs.get("cve", [])):
        objects.append(make_vulnerability(cve, ts))

    seed = "bundle:" + "|".join(o["id"] for o in objects)
    bundle_id = "bundle--" + str(uuid.uuid5(NAMESPACE, seed))
    return {"type": "bundle", "id": bundle_id, "objects": objects}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    import ioc_defang

    parser = argparse.ArgumentParser(
        prog="stix_export",
        description="Build a STIX 2.1 bundle skeleton from text/IOCs (offline).",
    )
    parser.add_argument("text", nargs="?", help="text to mine (or stdin if omitted)")
    parser.add_argument("--created", help="ISO8601 timestamp for created/modified")
    args = parser.parse_args(argv)

    text = args.text if args.text is not None else sys.stdin.read()
    iocs = ioc_defang.extract_iocs(text)
    bundle = build_bundle(iocs, created=args.created)
    print(json.dumps(bundle, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
