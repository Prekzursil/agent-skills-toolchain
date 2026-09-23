"""Tests for stix_export: STIX 2.1 bundle skeleton from IOCs (no network).

Run with any Python 3.10+ (stdlib only):
    python3 -m pytest .agents/skills/cti-lookup/tests/ -v
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import stix_export as sx  # noqa: E402

FIXED = "2023-05-01T00:00:00.000Z"


# --------------------------------------------------------------------------- #
# patterns
# --------------------------------------------------------------------------- #
def test_pattern_ipv4():
    assert sx.stix_pattern("ipv4", "1.2.3.4") == "[ipv4-addr:value = '1.2.3.4']"


def test_pattern_domain_url_email():
    assert sx.stix_pattern("domain", "evil.com") == "[domain-name:value = 'evil.com']"
    assert (
        sx.stix_pattern("url", "http://evil.com") == "[url:value = 'http://evil.com']"
    )
    assert sx.stix_pattern("email", "a@b.com") == "[email-addr:value = 'a@b.com']"


def test_pattern_hashes():
    assert sx.stix_pattern("md5", "d41d8cd98f00b204e9800998ecf8427e") == (
        "[file:hashes.'MD5' = 'd41d8cd98f00b204e9800998ecf8427e']"
    )
    assert sx.stix_pattern("sha1", "a" * 40) == (
        "[file:hashes.'SHA-1' = '" + "a" * 40 + "']"
    )
    assert sx.stix_pattern("sha256", "b" * 64) == (
        "[file:hashes.'SHA-256' = '" + "b" * 64 + "']"
    )


def test_pattern_escapes_single_quote():
    assert sx.stix_pattern("url", "http://x/a'b") == "[url:value = 'http://x/a\\'b']"


def test_pattern_unknown_type_raises():
    with pytest.raises(ValueError):
        sx.stix_pattern("not-a-type", "x")


# --------------------------------------------------------------------------- #
# indicator SDO
# --------------------------------------------------------------------------- #
def test_indicator_schema():
    ind = sx.make_indicator("ipv4", "1.2.3.4", created=FIXED)
    assert ind["type"] == "indicator"
    assert ind["spec_version"] == "2.1"
    assert ind["id"].startswith("indicator--")
    assert ind["pattern_type"] == "stix"
    assert ind["pattern"] == "[ipv4-addr:value = '1.2.3.4']"
    assert ind["created"] == FIXED
    assert ind["modified"] == FIXED
    assert ind["valid_from"] == FIXED
    assert ind["indicator_types"] == ["malicious-activity"]


def test_indicator_id_is_deterministic():
    a = sx.make_indicator("domain", "evil.com", created=FIXED)
    b = sx.make_indicator("domain", "evil.com", created="2099-01-01T00:00:00.000Z")
    # ID is derived from type+value only, so timestamps do not change it.
    assert a["id"] == b["id"]


def test_indicator_id_differs_by_value():
    a = sx.make_indicator("domain", "evil.com", created=FIXED)
    b = sx.make_indicator("domain", "good.com", created=FIXED)
    assert a["id"] != b["id"]


# --------------------------------------------------------------------------- #
# bundle
# --------------------------------------------------------------------------- #
def test_build_bundle_from_iocs():
    iocs = {
        "ipv4": ["1.2.3.4"],
        "domain": ["evil.com"],
        "cve": ["CVE-2021-44228"],
    }
    bundle = sx.build_bundle(iocs, created=FIXED)
    assert bundle["type"] == "bundle"
    assert bundle["id"].startswith("bundle--")
    types = [o["type"] for o in bundle["objects"]]
    assert types.count("indicator") == 2
    assert types.count("vulnerability") == 1


def test_cve_becomes_vulnerability_sdo():
    bundle = sx.build_bundle({"cve": ["CVE-2021-44228"]}, created=FIXED)
    vuln = bundle["objects"][0]
    assert vuln["type"] == "vulnerability"
    assert vuln["name"] == "CVE-2021-44228"
    assert vuln["external_references"][0]["external_id"] == "CVE-2021-44228"
    assert vuln["external_references"][0]["source_name"] == "cve"


def test_bundle_id_is_deterministic_for_same_iocs():
    iocs = {"ipv4": ["1.2.3.4"], "domain": ["evil.com"]}
    a = sx.build_bundle(iocs, created=FIXED)
    b = sx.build_bundle(iocs, created="2099-01-01T00:00:00.000Z")
    assert a["id"] == b["id"]


def test_bundle_is_json_serializable():
    bundle = sx.build_bundle({"ipv4": ["9.9.9.9"]}, created=FIXED)
    text = json.dumps(bundle)
    assert "indicator--" in text


def test_empty_iocs_yields_empty_object_list():
    bundle = sx.build_bundle({}, created=FIXED)
    assert bundle["type"] == "bundle"
    assert bundle["objects"] == []


def test_objects_are_ordered_deterministically():
    iocs = {"domain": ["b.com", "a.com"]}
    bundle = sx.build_bundle(iocs, created=FIXED)
    names = [o["pattern"] for o in bundle["objects"]]
    assert names == [
        "[domain-name:value = 'a.com']",
        "[domain-name:value = 'b.com']",
    ]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_text_to_bundle(capsys):
    rc = sx.main(["beacon to bad[.]example[.]com CVE-2021-44228", "--created", FIXED])
    assert rc == 0
    bundle = json.loads(capsys.readouterr().out)
    assert bundle["type"] == "bundle"
    types = sorted({o["type"] for o in bundle["objects"]})
    assert types == ["indicator", "vulnerability"]


def test_cli_empty_input_still_valid_bundle(capsys):
    rc = sx.main(["nothing here", "--created", FIXED])
    assert rc == 0
    bundle = json.loads(capsys.readouterr().out)
    assert bundle["objects"] == []
