#!/usr/bin/env python3
"""Text-level guards for ``deploy/searxng-min/settings.yml`` (Wave 1 items 1b + 5).

The repo ships no pyyaml at runtime, so these tests read the YAML as TEXT with a
tiny stanza scanner that understands exactly the shape this file uses (a
top-level ``engines:`` list of ``- name:`` items with flat ``key: value`` lines
and one optional nested ``about:`` block). They pin:

* the default-mix flips: ``google`` OFF (keyless Google scraping is dead),
  ``mwmbl`` + ``marginalia`` ON (``inactive: false`` + ``api_key: public``), so
  nobody silently re-enables google or re-buries the independent indexes;
* the clearnet ``vormweb`` xpath stanza under category ``onion index`` -- NOT the
  literal ``onions`` that stock SearXNG hard-gates on Tor -- with no ``.onion``
  host anywhere in it (index-only envelope);
* the Ahmia stanza + the ``remove`` list of Tor-only defaults staying intact, and
  no Tor/SOCKS proxy sneaking into the file.

When pyyaml happens to be installed the file is additionally parsed for real
(unique names / shortcuts); that test skips cleanly otherwise.
"""

from __future__ import annotations

import os
import re

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = os.path.join(HUB_DIR, "deploy", "searxng-min", "settings.yml")


def _read() -> str:
    with open(SETTINGS, encoding="utf-8") as fh:
        return fh.read()


def _strip_comment(line: str) -> str:
    """Drop a trailing ``# ...`` comment (the file never puts ``#`` inside values)."""
    return re.split(r"\s+#", line, maxsplit=1)[0].rstrip()


def _engine_stanzas(text: str) -> dict[str, dict]:
    """``{engine name: {key: value, ..., "about": {...}}}`` for the top-level
    ``engines:`` list. Values are the raw YAML scalars as text (``"true"``,
    ``"[onion index]"``...). Stops at the next top-level key."""
    lines = text.splitlines()
    try:
        start = lines.index("engines:")
    except ValueError:
        raise AssertionError("no top-level `engines:` list in settings.yml") from None
    stanzas: dict[str, dict] = {}
    current: dict | None = None
    nested: str | None = None
    for raw in lines[start + 1 :]:
        line = _strip_comment(raw)
        if not line.strip():
            continue
        if not line.startswith(" "):
            break  # next top-level key
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        if indent == 2 and body.startswith("- name:"):
            current = {}
            nested = None
            stanzas[body.split(":", 1)[1].strip()] = current
            continue
        assert current is not None, f"engine line before any `- name:`: {raw!r}"
        key, _, value = body.partition(":")
        key, value = key.strip(), value.strip()
        if indent == 4:
            if value == "":
                nested = key
                current[key] = {}
            else:
                nested = None
                current[key] = value
        elif indent >= 6 and nested is not None:
            current[nested][key] = value
        else:
            raise AssertionError(f"unexpected engine line shape: {raw!r}")
    return stanzas


def _category_tokens(value: str) -> list[str]:
    """Categories as SearXNG sees them: a scalar CSV or a ``[a, b]`` flow list."""
    inner = value.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    return [tok.strip().strip("'\"") for tok in inner.split(",") if tok.strip()]


# --------------------------------------------------------------------------- #
# item 1b: default-mix flips
# --------------------------------------------------------------------------- #
def test_google_is_disabled_in_the_minimal_settings():
    stanzas = _engine_stanzas(_read())
    assert stanzas["google"]["disabled"] == "true", (
        "keyless Google scraping is dead (Whoogle EOL 2026-07-24, searxng/searxng#6359 "
        "closed 2026-08-23) -- do not re-enable google here"
    )


def test_mwmbl_and_marginalia_are_enabled():
    stanzas = _engine_stanzas(_read())
    assert stanzas["mwmbl"]["disabled"] == "false"
    marginalia = stanzas["marginalia"]
    assert marginalia["disabled"] == "false"
    # Upstream ships `inactive: true`, which stops the module from loading at all;
    # both flips are required for the engine to exist.
    assert marginalia["inactive"] == "false"
    assert marginalia["api_key"] == "public"


def test_flip_evidence_is_recorded_beside_the_flips():
    text = _read()
    assert "6359" in text and "Whoogle" in text  # google-is-dead evidence
    assert "2026-" in text  # dated


# --------------------------------------------------------------------------- #
# item 5: VormWeb clearnet `onion index` xpath engine
# --------------------------------------------------------------------------- #
def test_vormweb_stanza_is_a_clearnet_xpath_engine_in_the_onion_index_category():
    stanzas = _engine_stanzas(_read())
    vw = stanzas["vormweb"]
    assert vw["engine"] == "xpath"  # upstream ships no vormweb engine; ours to carry
    assert vw["search_url"] == "https://vormweb.de/en/search?q={query}"
    assert vw["results_xpath"] == '//div[@class="query-box"]'
    assert vw["url_xpath"] == './/a[@id="urllink"]/@href'
    assert vw["title_xpath"] == './/a[@id="urllink"]'
    assert vw["content_xpath"] == ".//li/i"
    assert vw["shortcut"] == "vw"
    assert vw["disabled"] == "false"  # G-7: DEFAULT-ON
    assert float(vw["timeout"]) == 8.0
    cats = _category_tokens(vw["categories"])
    assert cats == ["onion index"]
    assert "onions" not in cats  # literal `onions` = Tor-gated by stock SearXNG
    # `about` uses only EngineAbout keys (unknown keys make the engine fail to load).
    about = vw["about"]
    assert about["website"].startswith("https://vormweb.de")
    assert about["use_official_api"] == "false" and about["require_api_key"] == "false"
    assert set(about) <= {
        "website",
        "wikidata_id",
        "official_api_documentation",
        "use_official_api",
        "require_api_key",
        "results",
        "description",
    }


def test_vormweb_stanza_never_points_at_an_onion_host():
    stanzas = _engine_stanzas(_read())
    flat = " ".join(
        v if isinstance(v, str) else " ".join(v.values())
        for v in stanzas["vormweb"].values()
    )
    # Clearnet vormweb.de only; results are index entries, never fetched.
    assert ".onion" not in flat
    assert "vormweb.de" in flat


def test_vormweb_caveats_are_documented_in_the_yaml():
    text = _read().lower()
    assert "self-declared" in text  # filtering is VormWeb's own policy, unverifiable
    assert "consent" in text and "unresolved" in text  # operator consent (envelope)
    assert "g-7" in text  # the owner decision that authorised the second engine


# --------------------------------------------------------------------------- #
# envelope invariants that must survive both items
# --------------------------------------------------------------------------- #
def test_ahmia_stanza_and_tor_only_removals_are_untouched():
    text = _read()
    stanzas = _engine_stanzas(text)
    ahmia = stanzas["ahmia"]
    assert ahmia["engine"] == "ahmia"
    assert ahmia["disabled"] == "false"
    assert _category_tokens(ahmia["categories"]) == ["onion index"]
    assert ahmia["shortcut"] == "ah"
    assert ahmia["base_url"] == "https://ahmia.fi"
    assert ahmia["search_url"] == "https://ahmia.fi/search/?{query}"
    assert float(ahmia["timeout"]) == 10.0
    # The Tor-gated onion-only defaults stay removed.
    remove_block = text.split("remove:", 1)[1].split("\n\n", 1)[0]
    assert re.search(r"^\s*-\s*ahmia\b", remove_block, re.M)
    assert re.search(r"^\s*-\s*torch\b", remove_block, re.M)


def test_no_engine_uses_the_literal_onions_category():
    for name, stanza in _engine_stanzas(_read()).items():
        cats = _category_tokens(stanza.get("categories", ""))
        assert "onions" not in cats, name


def test_no_tor_or_socks_proxy_is_configured():
    # Comments may (and do) say "NO Tor/SOCKS proxy"; the CONFIG lines must not
    # contain a proxy at all.
    config_lines = [
        _strip_comment(line)
        for line in _read().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    config = "\n".join(config_lines).lower()
    assert "socks" not in config
    assert "using_tor_proxy: true" not in config
    assert not re.search(r"^\s*proxies:", config, re.M)
    assert not re.search(r"^outgoing:", config, re.M)


def test_json_format_is_still_enabled():
    text = _read()
    formats = text.split("search:", 1)[1].split("\n\n", 1)[0]
    assert re.search(r"^\s*-\s*json\s*$", formats, re.M)


def test_settings_parse_as_yaml_when_pyyaml_is_available():
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load(_read())
    engines = data["engines"]
    names = [e["name"] for e in engines]
    assert len(names) == len(set(names))
    shortcuts = [e["shortcut"] for e in engines if "shortcut" in e]
    assert len(shortcuts) == len(set(shortcuts))
    by_name = {e["name"]: e for e in engines}
    assert by_name["google"]["disabled"] is True
    assert by_name["mwmbl"]["disabled"] is False
    assert by_name["marginalia"]["inactive"] is False
    assert by_name["vormweb"]["categories"] == ["onion index"]
    assert by_name["ahmia"]["categories"] == "onion index"
    assert data["use_default_settings"]["engines"]["remove"] == ["ahmia", "torch"]
    assert "json" in data["search"]["formats"]
