"""Tests for ioc_defang: defang/refang + offline IOC extraction (no network).

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

import ioc_defang as iocd  # noqa: E402


# --------------------------------------------------------------------------- #
# defang
# --------------------------------------------------------------------------- #
def test_defang_url_neutralizes_scheme_and_dots():
    assert iocd.defang("https://evil.com/a.php") == "hxxps://evil[.]com/a[.]php"


def test_defang_http_and_ipv4():
    assert iocd.defang("http://1.2.3.4/x") == "hxxp://1[.]2[.]3[.]4/x"


def test_defang_email():
    assert iocd.defang("alice@evil.com") == "alice[@]evil[.]com"


def test_defang_is_idempotent_on_already_safe_text():
    once = iocd.defang("evil.com")
    assert once == "evil[.]com"


# --------------------------------------------------------------------------- #
# refang
# --------------------------------------------------------------------------- #
def test_refang_bracketed_dot_variants():
    assert iocd.refang("evil[.]com") == "evil.com"
    assert iocd.refang("evil(.)com") == "evil.com"
    assert iocd.refang("evil{.}com") == "evil.com"


def test_refang_dot_word_and_at_word():
    assert iocd.refang("evil[dot]com") == "evil.com"
    assert iocd.refang("alice[at]evil[dot]com") == "alice@evil.com"


def test_refang_scheme_case_insensitive():
    assert iocd.refang("hXXps://evil[.]com") == "https://evil.com"
    assert iocd.refang("hxxp://1[.]2[.]3[.]4") == "http://1.2.3.4"


def test_refang_backslash_escaped_dot():
    assert iocd.refang(r"evil\.com") == "evil.com"


# --------------------------------------------------------------------------- #
# roundtrip property
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "value",
    [
        "https://evil.com/p.php",
        "http://1.2.3.4/x",
        "alice@evil.com",
        "sub.domain.evil.com",
        "1.2.3.4",
    ],
)
def test_refang_defang_roundtrip(value):
    assert iocd.refang(iocd.defang(value)) == value


# --------------------------------------------------------------------------- #
# extraction (offline)
# --------------------------------------------------------------------------- #
SAMPLE = (
    "Beacon to hxxps://bad[.]example[.]com/gate.php and 8[.]8[.]8[.]8 . "
    "Contact mule[at]evil[.]com about CVE-2021-44228. "
    "Payload md5 44d88612fea8a8f36de82e1278abb02f "
    "sha1 da39a3ee5e6b4b0d3255bfef95601890afd80709 "
    "sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)


def test_extract_refangs_then_finds_ipv4():
    iocs = iocd.extract_iocs(SAMPLE)
    assert "8.8.8.8" in iocs["ipv4"]


def test_extract_url_email_cve():
    iocs = iocd.extract_iocs(SAMPLE)
    assert "https://bad.example.com/gate.php" in iocs["url"]
    assert "mule@evil.com" in iocs["email"]
    assert "CVE-2021-44228" in iocs["cve"]


def test_extract_hashes_by_length():
    iocs = iocd.extract_iocs(SAMPLE)
    assert "44d88612fea8a8f36de82e1278abb02f" in iocs["md5"]
    assert "da39a3ee5e6b4b0d3255bfef95601890afd80709" in iocs["sha1"]
    assert (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        in iocs["sha256"]
    )
    # A 64-char hash must not also be miscounted as md5/sha1.
    assert len(iocs["md5"]) == 1
    assert len(iocs["sha1"]) == 1


def test_extract_domain_excludes_those_inside_url_or_email():
    iocs = iocd.extract_iocs(SAMPLE)
    # bad.example.com only appears inside the URL; evil.com only in the email.
    assert "bad.example.com" not in iocs["domain"]
    assert "evil.com" not in iocs["domain"]


def test_extract_standalone_domain_is_captured():
    iocs = iocd.extract_iocs("traffic seen to cdn.malware-c2[.]net today")
    assert "cdn.malware-c2.net" in iocs["domain"]


def test_extract_lists_are_sorted_and_unique():
    iocs = iocd.extract_iocs("1.1.1.1 1.1.1.1 2.2.2.2")
    assert iocs["ipv4"] == ["1.1.1.1", "2.2.2.2"]


def test_extract_empty_text_yields_empty_lists():
    iocs = iocd.extract_iocs("nothing to see here")
    assert all(v == [] for v in iocs.values())


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_defang(capsys):
    rc = iocd.main(["defang", "https://evil.com"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "hxxps://evil[.]com"


def test_cli_refang(capsys):
    rc = iocd.main(["refang", "hxxps://evil[.]com"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "https://evil.com"


def test_cli_extract_json(capsys):
    rc = iocd.main(["extract", "beacon 8[.]8[.]8[.]8", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ipv4"] == ["8.8.8.8"]


def test_cli_requires_subcommand():
    with pytest.raises(SystemExit):
        iocd.main([])
