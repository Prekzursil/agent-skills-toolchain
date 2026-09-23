#!/usr/bin/env python3
"""Unit tests for the in-process ``read_url`` adapter: Cloudflare markdown
negotiation, the optional readability rung (trafilatura / rs-trafilatura), the
stdlib tag-stripping fallback, the page_type heuristic and DNS re-resolution.

Runs against a REAL loopback fake origin (``fake_page_backend``) so the default
stdlib ``urllib`` fetch path, the content negotiation, the manual redirect loop
and the size cap are all exercised with NO network. Safety refusals (.onion,
non-http schemes, private/loopback targets, redirect caps, credentials in URLs)
are pinned with a fetch spy proving that NO request was made.

The fake origin lives on 127.0.0.1, which the adapter refuses by default, so the
tests that must reach it pass ``READ_URL_ALLOW_PRIVATE=1`` in the adapter's own
``environ`` -- the documented test/dev escape hatch, never ``os.environ``.

``trafilatura`` / ``rs_trafilatura`` are OPTIONAL imports and CI is stdlib-only,
so an autouse fixture forces BOTH absent (``None`` in ``sys.modules``) and the
readability tests inject fake modules exposing exactly the call surface the
adapter uses (``extract(...)`` / ``bare_extraction(...)``; rs: ``extract(...)``
returning an ``ExtractResult``-shaped object). The suite therefore behaves the
same on a box that has the real libraries installed.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import types

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HUB_DIR)
sys.path.insert(0, TESTS_DIR)

import accounts  # noqa: E402
import adapters  # noqa: E402
import hub  # noqa: E402
import rotation  # noqa: E402

import fake_page_backend as fake  # noqa: E402

ALLOW = {"READ_URL_ALLOW_PRIVATE": "1"}


@pytest.fixture(scope="module")
def origin():
    server, base = fake.start_server()
    try:
        yield base
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def _reset_fake():
    fake.reset()
    yield
    fake.reset()


@pytest.fixture(autouse=True)
def _no_readability_extractors(monkeypatch):
    """Both optional extractors ABSENT unless a test installs a fake: ``None`` in
    ``sys.modules`` makes ``import trafilatura`` raise ImportError even where the
    real package is installed, so the v0 expectations hold everywhere."""
    monkeypatch.setitem(sys.modules, "trafilatura", None)
    monkeypatch.setitem(sys.modules, "rs_trafilatura", None)


def _install_fake_trafilatura(monkeypatch, extract, bare=None, calls=None):
    """Fake the OPTIONAL ``trafilatura`` module through ``sys.modules``.

    ``extract(html, url, kwargs)`` and ``bare(html, url, kwargs)`` are plain test
    callables; the fake exposes trafilatura's real surface (``extract(filecontent,
    url=None, **kw)`` / ``bare_extraction(filecontent, url=None, **kw)``) and logs
    every call as ``(function, url, kwargs)`` into ``calls``. Returns ``calls``.
    """
    log: list = calls if calls is not None else []
    mod = types.ModuleType("trafilatura")
    mod.__version__ = "0.0-fake"

    def _extract(filecontent, url=None, **kwargs):
        log.append(("extract", url, dict(kwargs)))
        return extract(filecontent, url, kwargs)

    def _bare_extraction(filecontent, url=None, **kwargs):
        log.append(("bare_extraction", url, dict(kwargs)))
        if bare is None:
            return None
        return bare(filecontent, url, kwargs)

    mod.extract = _extract
    mod.bare_extraction = _bare_extraction
    monkeypatch.setitem(sys.modules, "trafilatura", mod)
    return log


def _install_fake_rs_trafilatura(monkeypatch, extract, calls=None):
    """Fake the OPTIONAL Rust build: ``rs_trafilatura.extract(html, *, url=None,
    **kw)`` returns an ``ExtractResult``-shaped object (title, author, date,
    main_content, content_markdown, page_type, extraction_quality)."""
    log: list = calls if calls is not None else []
    mod = types.ModuleType("rs_trafilatura")

    def _extract(html, *, url=None, **kwargs):
        log.append(("extract", url, dict(kwargs)))
        return extract(html, url, kwargs)

    mod.extract = _extract
    monkeypatch.setitem(sys.modules, "rs_trafilatura", mod)
    return log


def _rs_result(**overrides):
    base = dict(
        title="Rust title",
        author="R. Author",
        date="2026-01-02",
        main_content="plain text body " * 20,
        content_markdown="# Rust title\n\n" + "markdown body paragraph. " * 20,
        page_type="article",
        extraction_quality=0.93,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _doc(**fields):
    """A trafilatura 2.x ``Document``-shaped metadata object."""
    return types.SimpleNamespace(
        **{"title": None, "author": None, "date": None, **fields}
    )


LONG_MD = "## Heading\n\n" + ("A sentence of real article prose. " * 12).strip()
SHORT_MD = "Too short."


def _spy_fetch(calls: list):
    def fetch(url, headers, timeout, max_bytes):
        calls.append(url)
        return adapters._urllib_fetch(url, headers, timeout, max_bytes)

    return fetch


def _adapter(environ=None, fetch=None, resolver=None):
    return adapters.ReadUrlAdapter(
        environ=ALLOW if environ is None else environ, fetch=fetch, resolver=resolver
    )


def _payload(result: dict) -> dict:
    assert not result["isError"], result
    return json.loads(result["content"][0]["text"])


def _error_text(result: dict) -> str:
    assert result["isError"] is True, result
    return result["content"][0]["text"]


# --------------------------------------------------------------------------- #
# surface
# --------------------------------------------------------------------------- #
def test_tool_surface_is_one_honest_tool():
    ad = _adapter()
    assert ad.tool_names() == ["read_url"]
    d = ad.tool_defs()[0]
    assert d["inputSchema"]["required"] == ["url"]
    assert set(d["inputSchema"]["properties"]) == {"url", "max_bytes", "timeout_s"}
    desc = d["description"].lower()
    assert "not readability" in desc  # the fallback is honest about being tag-stripping
    assert "cloudflare" in desc and ".onion" in desc
    report = ad.capabilities()
    assert report["provider"] == "read_url" and report["self_hosted"] is False
    assert report["keyless"] is True
    assert [t["state"] for t in report["tools"]] == ["native"]
    assert report["private_targets_allowed"] is True
    assert _adapter(environ={}).capabilities()["private_targets_allowed"] is False


# --------------------------------------------------------------------------- #
# (a) Cloudflare markdown path
# --------------------------------------------------------------------------- #
def test_cloudflare_markdown_negotiated_is_high_quality_with_tokens(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/cf"}))
    assert payload["extractor"] == "cloudflare-markdown"
    assert payload["quality"] == "high"
    assert payload["content_type"] == "text/markdown"
    assert payload["tokens"] == {"markdown": 123, "original": 4567}
    assert payload["title"] == "Markdown for Agents"  # from the YAML frontmatter
    assert payload["markdown"].startswith("---\ntitle:")
    assert "# Markdown for Agents" in payload["markdown"]
    assert "text" not in payload  # one body key per extractor path
    assert payload["status"] == 200 and payload["truncated"] is False
    assert payload["url"] == payload["final_url"] == origin + "/cf"
    assert payload["redirects"] == 0
    sent = fake.RECEIVED[0]["headers"]
    # The negotiation header, exactly as Cloudflare documents it.
    assert sent["accept"].startswith("text/markdown, text/html;q=0.9")
    assert "search-hub" in sent["user-agent"]
    assert "cookie" not in sent and "authorization" not in sent


# --------------------------------------------------------------------------- #
# (b) stdlib HTML fallback
# --------------------------------------------------------------------------- #
def test_html_fallback_strips_boilerplate_keeps_title_and_paragraphs(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "stdlib-text"
    assert payload["quality"] == "low"
    assert payload["content_type"] == "text/html"
    assert "tokens" not in payload and "markdown" not in payload
    assert (
        payload["title"] == "Example Page \u2014 Read Me"
    )  # entity decoded, ws collapsed
    text = payload["text"]
    assert (
        "SKIP-" not in text
    )  # script/style/noscript/svg/template/nav/footer/aside/header
    assert "First heading" in text
    assert "Tom & Jerry went to the market \u2014 it was busy, very busy." in text
    assert "Second paragraph with an inline link and inline code." in text
    assert "alpha\nbeta" in text  # list items keep line breaks
    assert "First heading\n\nTom & Jerry" in text  # paragraph breaks kept
    assert "  " not in text.replace("\n", "")  # whitespace collapsed
    assert "low" in payload["note"] and "trafilatura" in payload["note"].lower()


def test_plain_text_passes_through_with_collapsed_blank_lines(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/plain"}))
    assert payload["extractor"] == "stdlib-text" and payload["quality"] == "low"
    assert payload["text"] == "just plain\n\ntext"
    assert payload["title"] is None


def test_declared_charset_is_honoured(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/latin1"}))
    assert payload["title"] == "Caf\u00e9" and "na\u00efve" in payload["text"]


# --------------------------------------------------------------------------- #
# (c) .onion refused, (d) non-http schemes refused -- before ANY request
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url",
    [
        "http://expyuzz4wqqyqhjn.onion/",
        "https://something.ONION./page",
        "http://user@abc.onion:8080/x",
    ],
)
def test_onion_urls_refused_without_any_request(url):
    calls: list = []
    text = _error_text(
        _adapter(fetch=_spy_fetch(calls)).handle_call("read_url", {"url": url})
    )
    assert ".onion" in text and "envelope" in text.lower()
    assert calls == []


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://ftp.example.test/pub/x",
        "javascript:alert(1)",
        "data:text/html,hi",
        "gopher://x",
        "//no-scheme.example/x",
        "example.com/no-scheme",
    ],
)
def test_non_http_schemes_refused_without_any_request(url):
    calls: list = []
    text = _error_text(
        _adapter(fetch=_spy_fetch(calls)).handle_call("read_url", {"url": url})
    )
    assert "http" in text and "https" in text
    assert calls == []


def test_credentials_in_url_are_refused_never_sent():
    calls: list = []
    text = _error_text(
        _adapter(fetch=_spy_fetch(calls)).handle_call(
            "read_url", {"url": "http://alice:secret@127.0.0.1:9/x"}
        )
    )
    assert "credentials" in text.lower() and "secret" not in text
    assert calls == []


# --------------------------------------------------------------------------- #
# (e) redirects: followed up to 5 hops, re-checked each hop, loops refused
# --------------------------------------------------------------------------- #
def test_redirect_loop_is_refused_after_the_hop_cap(origin):
    calls: list = []
    text = _error_text(
        _adapter(fetch=_spy_fetch(calls)).handle_call(
            "read_url", {"url": origin + "/loop"}
        )
    )
    assert "too many redirects" in text and "5" in text
    assert (
        len(calls) == adapters.READ_URL_MAX_REDIRECTS + 1
    )  # initial + 5 hops, then stop


def test_five_redirects_are_followed_six_are_not(origin):
    ad = _adapter()
    payload = _payload(ad.handle_call("read_url", {"url": origin + "/hop/5"}))
    assert payload["redirects"] == 5
    assert (
        payload["final_url"] == origin + "/hop/0"
        and payload["url"] == origin + "/hop/5"
    )
    assert payload["title"] == "Example Page \u2014 Read Me"
    assert "too many redirects" in _error_text(
        ad.handle_call("read_url", {"url": origin + "/hop/6"})
    )


def test_redirect_to_onion_or_file_is_refused_at_the_hop(origin):
    calls: list = []
    ad = _adapter(fetch=_spy_fetch(calls))
    text = _error_text(ad.handle_call("read_url", {"url": origin + "/to-onion"}))
    assert ".onion" in text and len(calls) == 1  # the onion hop was never fetched
    calls.clear()
    text = _error_text(ad.handle_call("read_url", {"url": origin + "/to-file"}))
    assert "file" in text and len(calls) == 1


def test_redirect_without_location_is_an_error(origin):
    text = _error_text(
        _adapter().handle_call("read_url", {"url": origin + "/nolocation"})
    )
    assert "302" in text and "Location" in text


# --------------------------------------------------------------------------- #
# (f) private / loopback / link-local targets refused unless the escape hatch is set
# --------------------------------------------------------------------------- #
def test_loopback_refused_by_default_and_allowed_with_the_flag(origin):
    calls: list = []
    strict = _adapter(environ={}, fetch=_spy_fetch(calls))
    text = _error_text(strict.handle_call("read_url", {"url": origin + "/html"}))
    assert "private" in text.lower() and "READ_URL_ALLOW_PRIVATE" in text
    assert calls == []
    allowed = _adapter(environ=ALLOW, fetch=_spy_fetch(calls))
    payload = _payload(allowed.handle_call("read_url", {"url": origin + "/html"}))
    assert payload["status"] == 200 and len(calls) == 1


@pytest.mark.parametrize(
    "url, resolved",
    [
        ("http://intranet.test/", ["10.0.0.5"]),  # RFC1918 via DNS
        ("http://corp.test/", ["172.16.4.4"]),
        ("http://home.test/", ["192.168.1.1"]),
        ("http://meta.test/", ["169.254.169.254"]),  # cloud metadata, link-local
        ("http://six.test/", ["fd12::1"]),  # fc00::/7
        ("http://mapped.test/", ["::ffff:127.0.0.1"]),  # IPv4-mapped loopback
        ("http://mixed.test/", ["93.184.216.34", "10.0.0.1"]),  # ANY private answer
        ("http://169.254.169.254/latest/meta-data/", None),  # literal, no DNS
        ("http://[::1]:80/", None),
        ("http://0.0.0.0/", None),
    ],
)
def test_private_targets_refused_without_fetch(url, resolved):
    calls: list = []
    ad = _adapter(
        environ={},
        fetch=_spy_fetch(calls),
        resolver=(lambda _h: resolved) if resolved else None,
    )
    text = _error_text(ad.handle_call("read_url", {"url": url}))
    assert "private" in text.lower() or "loopback" in text.lower()
    assert calls == []


def test_redirect_into_private_space_is_refused_at_the_hop(origin):
    calls: list = []
    # The fake origin is loopback too, so the injected resolver pretends hop 1 is
    # public and lets only the redirect target resolve into RFC1918 space.
    resolved = {"127.0.0.1": ["93.184.216.34"], "intranet.test": ["10.0.0.5"]}
    ad = _adapter(environ={}, fetch=_spy_fetch(calls), resolver=lambda h: resolved[h])
    text = _error_text(ad.handle_call("read_url", {"url": origin + "/to-private"}))
    assert "private" in text.lower() and len(calls) == 1


def test_unresolvable_host_is_truthful_error():
    calls: list = []

    def failing(_host):
        raise socket.gaierror("Name or service not known")

    text = _error_text(
        _adapter(environ={}, fetch=_spy_fetch(calls), resolver=failing).handle_call(
            "read_url", {"url": "http://does-not-resolve.invalid/"}
        )
    )
    assert "resolve" in text.lower() and calls == []


# --------------------------------------------------------------------------- #
# (g) size cap
# --------------------------------------------------------------------------- #
def test_size_cap_marks_truncated(origin):
    payload = _payload(
        _adapter().handle_call("read_url", {"url": origin + "/big", "max_bytes": 1000})
    )
    assert payload["truncated"] is True
    assert len(payload["text"].encode("utf-8")) <= 1000
    assert payload["bytes"] <= 1000  # the fetch stops reading at the cap
    full = _payload(_adapter().handle_call("read_url", {"url": origin + "/big"}))
    assert full["truncated"] is False and full["bytes"] == len(fake.BIG_BODY)


# --------------------------------------------------------------------------- #
# truthful errors: non-2xx, binary, unreachable, bad arguments
# --------------------------------------------------------------------------- #
def test_non_2xx_is_truthful_error(origin):
    text = _error_text(_adapter().handle_call("read_url", {"url": origin + "/404"}))
    assert "HTTP 404" in text and "/404" in text


def test_binary_content_type_is_refused_truthfully(origin):
    text = _error_text(_adapter().handle_call("read_url", {"url": origin + "/binary"}))
    assert "application/pdf" in text and "text" in text.lower()


def test_unreachable_origin_is_truthful_error():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()  # nothing listens here now
    text = _error_text(
        _adapter().handle_call(
            "read_url", {"url": f"http://127.0.0.1:{port}/", "timeout_s": 2}
        )
    )
    assert "request failed" in text and "fabricated" in text


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'url' is required"),
        ({"url": 42}, "'url' is required"),
        ({"url": "http://example.test/", "max_bytes": 10}, "'max_bytes' must be"),
        ({"url": "http://example.test/", "max_bytes": "big"}, "'max_bytes' must be"),
        ({"url": "http://example.test/", "timeout_s": 0}, "'timeout_s' must be"),
        ({"url": "http://example.test/", "timeout_s": 999}, "'timeout_s' must be"),
    ],
)
def test_argument_validation_happens_before_any_request(args, needle):
    calls: list = []
    text = _error_text(_adapter(fetch=_spy_fetch(calls)).handle_call("read_url", args))
    assert needle in text and calls == []


def test_unknown_tool_is_rejected():
    assert "unknown" in _error_text(_adapter().handle_call("nope", {}))


# --------------------------------------------------------------------------- #
# (h) wiring: default ON, ENABLE_READ_URL=0 kill switch, hub-level listing
# --------------------------------------------------------------------------- #
def test_wired_by_default_and_kill_switch():
    assert "read_url" in [a.platform for a in adapters.wired_adapters({})]
    for flag in ("0", "false", "no", "off"):
        platforms = [
            a.platform for a in adapters.wired_adapters({"ENABLE_READ_URL": flag})
        ]
        assert "read_url" not in platforms and "selfhosted" in platforms
    for flag in ("", "1", "true"):
        assert "read_url" in [
            a.platform for a in adapters.wired_adapters({"ENABLE_READ_URL": flag})
        ]
    # The lane-gated builder keeps its historical contract.
    assert [a.platform for a in adapters.default_adapters({})] == ["selfhosted"]


def _bare_hub(tmp_path, environ):
    store = accounts.AccountStore(str(tmp_path / "acc.json"), [], environ=environ)
    rot = rotation.Rotator.from_specs([], store, environ=environ)
    return hub.SearchHub(
        [], emit=lambda _line: None, store=store, rotator=rot, environ=environ
    )


def test_hub_lists_read_url_by_default_and_hides_it_when_killed(tmp_path):
    names = {t["name"] for t in _bare_hub(tmp_path, {}).all_tools}
    assert "read_url" in names
    killed = {
        t["name"] for t in _bare_hub(tmp_path, {"ENABLE_READ_URL": "0"}).all_tools
    }
    assert "read_url" not in killed and "selfhosted_search" in killed


def test_hub_routes_read_url_in_process(tmp_path, origin):
    captured: list = []
    store = accounts.AccountStore(str(tmp_path / "acc.json"), [], environ=ALLOW)
    rot = rotation.Rotator.from_specs([], store, environ=ALLOW)
    server = hub.SearchHub(
        [],
        emit=lambda line: captured.append(json.loads(line)),
        store=store,
        rotator=rot,
        environ=ALLOW,
    )
    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "read_url", "arguments": {"url": origin + "/cf"}},
        }
    )
    reply = captured[0]
    assert reply["id"] == 7 and reply["result"]["isError"] is False
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["extractor"] == "cloudflare-markdown"
    assert server._children == {}  # never spawns a subprocess


# --------------------------------------------------------------------------- #
# (i) Wave 2: the extractor ladder -- optional trafilatura rung, faked via
#     sys.modules (never installed in CI), between markdown negotiation and the
#     stdlib fallback. Same tool name, same output shape, additive fields only.
# --------------------------------------------------------------------------- #
SIGNAL_KEYS = {
    "extractor_ladder",
    "page_type",
    "chars",
    "link_density",
    "boilerplate_removed",
    "min_chars",
    "author",
    "date",
}


def test_surface_and_capabilities_report_the_ladder(monkeypatch):
    ad = _adapter()
    desc = ad.tool_defs()[0]["description"].lower()
    assert "trafilatura" in desc and "extractor_ladder" in desc
    assert "page_type" in desc and "dns_rebound" in desc
    report = ad.capabilities()
    assert report["readability_extractor"] is None  # both optional modules absent
    assert report["min_chars"] == adapters.READ_URL_DEFAULT_MIN_CHARS == 200
    assert report["dns_rebound_check"] is False  # ALLOW environ skips the pin
    assert _adapter(environ={}).capabilities()["dns_rebound_check"] is True
    _install_fake_trafilatura(monkeypatch, extract=lambda *_a: LONG_MD)
    assert _adapter().capabilities()["readability_extractor"] == "trafilatura"
    _install_fake_rs_trafilatura(monkeypatch, extract=lambda *_a: _rs_result())
    assert _adapter().capabilities()["readability_extractor"] == "rs-trafilatura"


def test_trafilatura_present_is_chosen_high_with_metadata(origin, monkeypatch):
    calls = _install_fake_trafilatura(
        monkeypatch,
        extract=lambda _h, _u, _kw: LONG_MD,
        bare=lambda _h, _u, _kw: _doc(
            title="Meta Title", author="Ada Lovelace", date="2026-08-30"
        ),
    )
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "trafilatura"
    assert payload["quality"] == "high"
    assert payload["extractor_ladder"] == ["trafilatura"]
    assert payload["markdown"] == LONG_MD and "text" not in payload
    assert payload["chars"] == len(LONG_MD)
    assert payload["boilerplate_removed"] is True
    assert payload["min_chars"] == 200
    # metadata from bare_extraction wins over <title>; author/date exposed
    assert payload["title"] == "Meta Title"
    assert payload["author"] == "Ada Lovelace" and payload["date"] == "2026-08-30"
    assert payload["content_type"] == "text/html"
    assert "high" in payload["note"] and "trafilatura" in payload["note"]
    # exactly the documented call: precision pass once, metadata once
    kinds = [c[0] for c in calls]
    assert kinds == ["extract", "bare_extraction"]
    _fn, url, kwargs = calls[0]
    assert url == origin + "/html"
    assert kwargs["output_format"] == "markdown"
    assert kwargs["include_links"] is False and kwargs["include_tables"] is True
    assert kwargs["favor_recall"] is False
    assert calls[1][2]["with_metadata"] is True and calls[1][1] == origin + "/html"
    # the fake origin saw ONE request: extraction happens on the fetched body
    assert len(fake.RECEIVED) == 1


def test_short_precision_extract_retries_with_recall_labelled_medium(
    origin, monkeypatch
):
    def extract(_html, _url, kwargs):
        return LONG_MD if kwargs.get("favor_recall") else SHORT_MD

    calls = _install_fake_trafilatura(monkeypatch, extract=extract)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "trafilatura"
    assert payload["quality"] == "medium"
    assert payload["extractor_ladder"] == ["trafilatura", "trafilatura-recall"]
    assert payload["markdown"] == LONG_MD
    recall_flags = [c[2]["favor_recall"] for c in calls if c[0] == "extract"]
    assert recall_flags == [False, True]
    assert "medium" in payload["note"] and "200" in payload["note"]
    assert str(len(SHORT_MD)) in payload["note"]  # says how short the first pass was
    assert payload["title"] == "Example Page \u2014 Read Me"  # <title> fallback
    assert payload["author"] is None and payload["date"] is None


def test_trafilatura_empty_on_both_passes_falls_through_to_stdlib(origin, monkeypatch):
    calls = _install_fake_trafilatura(monkeypatch, extract=lambda *_a: None)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "stdlib-text" and payload["quality"] == "low"
    assert payload["extractor_ladder"] == [
        "trafilatura",
        "trafilatura-recall",
        "stdlib-text",
    ]
    assert "First heading" in payload["text"] and "markdown" not in payload
    assert payload["boilerplate_removed"] is False
    assert [c[0] for c in calls] == ["extract", "extract"]  # no metadata pass
    assert "trafilatura" in payload["note"] and "0 chars" in payload["note"]


def test_trafilatura_raising_falls_through_truthfully(origin, monkeypatch):
    def boom(*_a):
        raise RuntimeError("lxml exploded")

    _install_fake_trafilatura(monkeypatch, extract=boom)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "stdlib-text" and payload["quality"] == "low"
    assert payload["extractor_ladder"] == ["trafilatura", "stdlib-text"]
    assert "RuntimeError" in payload["note"] and "lxml exploded" in payload["note"]
    assert "First heading" in payload["text"]


def test_absent_module_is_skipped_by_the_ladder(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor_ladder"] == ["stdlib-text"]
    assert payload["extractor"] == "stdlib-text" and payload["quality"] == "low"
    assert "pip install trafilatura" in payload["note"]
    assert payload["author"] is None and payload["date"] is None


def test_markdown_negotiation_still_wins_before_any_extractor(origin, monkeypatch):
    calls = _install_fake_trafilatura(monkeypatch, extract=lambda *_a: LONG_MD)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/cf"}))
    assert payload["extractor"] == "cloudflare-markdown"
    assert payload["extractor_ladder"] == ["cloudflare-markdown"]
    assert payload["quality"] == "high" and payload["tokens"]["markdown"] == 123
    assert payload["boilerplate_removed"] is True  # Cloudflare cleaned it server-side
    assert calls == []  # the readability rung never ran


def test_old_trafilatura_without_markdown_output_falls_back_to_txt(origin, monkeypatch):
    def extract(_html, _url, kwargs):
        if kwargs["output_format"] == "markdown":
            raise AttributeError("Cannot set format, must be one of: txt, xml")
        return LONG_MD

    calls = _install_fake_trafilatura(monkeypatch, extract=extract)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "trafilatura" and payload["quality"] == "high"
    assert payload["text"] == LONG_MD and "markdown" not in payload
    assert [c[2]["output_format"] for c in calls if c[0] == "extract"] == [
        "markdown",
        "txt",
    ]
    assert payload["extractor_ladder"] == ["trafilatura"]
    assert "txt" in payload["note"]


def test_metadata_dict_variant_and_metadata_failure_are_tolerated(origin, monkeypatch):
    # trafilatura 1.x returned a dict from bare_extraction; 2.x a Document.
    _install_fake_trafilatura(
        monkeypatch,
        extract=lambda *_a: LONG_MD,
        bare=lambda *_a: {"title": "Dict Title", "author": "  ", "date": "2025-01-01"},
    )
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["title"] == "Dict Title"
    assert payload["author"] is None and payload["date"] == "2025-01-01"

    def bare_boom(*_a):
        raise ValueError("metadata failed")

    _install_fake_trafilatura(monkeypatch, extract=lambda *_a: LONG_MD, bare=bare_boom)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "trafilatura" and payload["quality"] == "high"
    assert payload["title"] == "Example Page \u2014 Read Me"  # <title> fallback
    assert payload["author"] is None and payload["date"] is None


def test_rs_trafilatura_is_preferred_and_labelled(origin, monkeypatch):
    tcalls = _install_fake_trafilatura(monkeypatch, extract=lambda *_a: LONG_MD)
    rcalls = _install_fake_rs_trafilatura(monkeypatch, extract=lambda *_a: _rs_result())
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "rs-trafilatura" and payload["quality"] == "high"
    assert payload["extractor_ladder"] == ["rs-trafilatura"]
    assert payload["markdown"].startswith("# Rust title")
    assert payload["title"] == "Rust title" and payload["author"] == "R. Author"
    assert payload["date"] == "2026-01-02"
    assert payload["extractor_confidence"] == 0.93
    assert payload["boilerplate_removed"] is True
    assert tcalls == []  # the Python build was not consulted
    _fn, url, kwargs = rcalls[0]
    assert url == origin + "/html"
    assert kwargs["output_markdown"] is True and kwargs["favor_recall"] is False
    assert kwargs["include_tables"] is True


def test_rs_trafilatura_failure_falls_to_trafilatura_then_stdlib(origin, monkeypatch):
    def rs_boom(*_a):
        raise OSError("bad wheel")

    _install_fake_rs_trafilatura(monkeypatch, extract=rs_boom)
    _install_fake_trafilatura(monkeypatch, extract=lambda *_a: LONG_MD)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "trafilatura" and payload["quality"] == "high"
    assert payload["extractor_ladder"] == ["rs-trafilatura", "trafilatura"]
    assert "OSError" in payload["note"] and "bad wheel" in payload["note"]
    assert "extractor_confidence" not in payload

    _install_fake_trafilatura(monkeypatch, extract=lambda *_a: None)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "stdlib-text"
    assert payload["extractor_ladder"] == [
        "rs-trafilatura",
        "trafilatura",
        "trafilatura-recall",
        "stdlib-text",
    ]


def test_rs_trafilatura_without_markdown_uses_main_content_as_text(origin, monkeypatch):
    _install_fake_rs_trafilatura(
        monkeypatch,
        extract=lambda *_a: _rs_result(content_markdown=None, extraction_quality=None),
    )
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "rs-trafilatura"
    assert payload["text"].startswith("plain text body") and "markdown" not in payload
    assert "extractor_confidence" not in payload


def test_recall_result_tiny_against_a_link_heavy_page_goes_to_stdlib(
    origin, monkeypatch
):
    # A listing page: trafilatura strips the links (include_links=False) and finds
    # almost nothing, while the visible page text is large -> the stdlib text is
    # the more useful answer and the note says so.
    def extract(_html, _url, kwargs):
        return "40 results." if kwargs.get("favor_recall") else None

    _install_fake_trafilatura(monkeypatch, extract=extract)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/listing"}))
    assert payload["extractor"] == "stdlib-text" and payload["quality"] == "low"
    assert payload["extractor_ladder"] == [
        "trafilatura",
        "trafilatura-recall",
        "stdlib-text",
    ]
    assert "Result item number 39" in payload["text"]
    assert "11 chars" in payload["note"]  # the recall pass result, reported


def test_recall_result_covering_a_genuinely_short_page_is_medium(origin, monkeypatch):
    def extract(_html, _url, kwargs):
        return "Hello world, tiny page." if kwargs.get("favor_recall") else None

    _install_fake_trafilatura(monkeypatch, extract=extract)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/short"}))
    assert payload["extractor"] == "trafilatura" and payload["quality"] == "medium"
    assert payload["markdown"] == "Hello world, tiny page."
    assert payload["chars"] == 23 and payload["page_type"] == "other"


def test_recall_result_on_a_textless_shell_page_is_not_medium(origin, monkeypatch):
    # Found by the manual smoke: on an app shell (no visible text) the real
    # rs-trafilatura recall pass returned the <title> three times ("AppAppApp");
    # a page with no visible text has nothing to cover, so that is NOT medium.
    def extract(_html, _url, kwargs):
        return "AppAppApp" if kwargs.get("favor_recall") else None

    _install_fake_trafilatura(monkeypatch, extract=extract)
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/shell"}))
    assert payload["extractor"] == "stdlib-text" and payload["quality"] == "low"
    assert payload["text"] == "" and payload["chars"] == 0
    assert payload["page_type"] == "shell"
    assert "9 chars" in payload["note"] and "0 chars" in payload["note"]


def test_metadata_whitespace_is_collapsed(origin, monkeypatch):
    # rs-trafilatura hands back <title> text verbatim ("Example   Page"); the
    # payload title is normalised the way <title> itself is.
    _install_fake_rs_trafilatura(
        monkeypatch,
        extract=lambda *_a: _rs_result(title="  Example \n  Page ", author="A.\tB."),
    )
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["title"] == "Example Page" and payload["author"] == "A. B."


def test_min_chars_env_moves_the_threshold(origin, monkeypatch):
    sixty = "x" * 60
    calls = _install_fake_trafilatura(monkeypatch, extract=lambda *_a: sixty)
    env = {**ALLOW, "READ_URL_MIN_CHARS": "50"}
    ad = _adapter(environ=env)
    assert ad.capabilities()["min_chars"] == 50
    payload = _payload(ad.handle_call("read_url", {"url": origin + "/html"}))
    assert payload["quality"] == "high" and payload["min_chars"] == 50
    assert [c[2]["favor_recall"] for c in calls if c[0] == "extract"] == [False]
    # default (200) would have sent the same 60 chars to the recall retry
    calls.clear()
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["quality"] == "medium" and payload["min_chars"] == 200
    assert [c[2]["favor_recall"] for c in calls if c[0] == "extract"] == [False, True]


@pytest.mark.parametrize("raw", ["abc", "0", "-5", "", " ", "1e3", "999999999"])
def test_min_chars_env_invalid_values_fall_back_to_the_default(raw):
    env = {**ALLOW, "READ_URL_MIN_CHARS": raw}
    assert _adapter(environ=env).capabilities()["min_chars"] == 200


def test_extraction_is_capped_and_marked_truncated(origin, monkeypatch):
    _install_fake_trafilatura(monkeypatch, extract=lambda *_a: LONG_MD * 40)
    payload = _payload(
        _adapter().handle_call("read_url", {"url": origin + "/html", "max_bytes": 600})
    )
    assert payload["extractor"] == "trafilatura" and payload["truncated"] is True
    assert len(payload["markdown"].encode("utf-8")) <= 600
    assert payload["chars"] == len(payload["markdown"])


# --------------------------------------------------------------------------- #
# (j) page_type heuristic + quality signals (stdlib, a hint only)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path, expected, density_check",
    [
        ("/html", "article", lambda d: d < 0.3),  # <article> present, prose
        ("/listing", "listing", lambda d: d > 0.5),  # link text dominates
        ("/docs", "docs", lambda d: d < 0.5),  # >= 2 code blocks
        ("/shell", "shell", lambda d: d == 0.0),  # scripts, no visible text
        ("/short", "other", lambda d: d == 0.0),  # tiny static page
        ("/plain", "other", lambda d: d == 0.0),  # not HTML: no signal
    ],
)
def test_page_type_heuristic_on_fixtures(origin, path, expected, density_check):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + path}))
    assert payload["page_type"] == expected, payload
    assert density_check(payload["link_density"]), payload["link_density"]
    assert 0.0 <= payload["link_density"] <= 1.0


def test_page_type_is_a_hint_also_for_negotiated_markdown(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/cf"}))
    assert payload["page_type"] == "article"  # one code fence, prose, no links
    assert payload["link_density"] == 0.0
    assert payload["boilerplate_removed"] is True
    assert payload["chars"] == len(payload["markdown"])


def test_quality_signals_are_present_on_every_path(origin, monkeypatch):
    for path in ("/html", "/plain", "/cf", "/listing"):
        payload = _payload(_adapter().handle_call("read_url", {"url": origin + path}))
        assert SIGNAL_KEYS <= set(payload), (path, sorted(payload))
        body = payload.get("markdown", payload.get("text"))
        assert payload["chars"] == len(body)
        assert payload["min_chars"] == 200
        assert isinstance(payload["extractor_ladder"], list)
        chosen = payload["extractor_ladder"][-1].replace("-recall", "")
        assert chosen == payload["extractor"]
        assert payload["page_type"] in ("article", "docs", "listing", "shell", "other")
    plain = _payload(_adapter().handle_call("read_url", {"url": origin + "/plain"}))
    assert plain["boilerplate_removed"] is False
    assert plain["extractor_ladder"] == ["stdlib-text"]
    html = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert html["boilerplate_removed"] is False  # tag-stripping is not readability
    _install_fake_trafilatura(monkeypatch, extract=lambda *_a: LONG_MD)
    upgraded = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert SIGNAL_KEYS <= set(upgraded)
    assert upgraded["page_type"] == "article"  # heuristic still reads the fetched HTML


# --------------------------------------------------------------------------- #
# (k) DNS pinning (cheap stdlib mitigation of the v0 TOCTOU gap): every address
#     is checked, the host is re-resolved after the fetch, a changed answer is a
#     dns_rebound error. Resolver injected; the fetch itself hits the fake origin.
# --------------------------------------------------------------------------- #
def _sequenced_resolver(answers: list, seen: list):
    """Answer ``answers[i]`` to the i-th call (last answer repeats); log hosts."""

    def resolve(host):
        seen.append(host)
        index = min(len(seen) - 1, len(answers) - 1)
        answer = answers[index]
        if isinstance(answer, Exception):
            raise answer
        return list(answer)

    return resolve


def test_dns_answer_changing_during_the_fetch_is_a_rebound_error(origin):
    calls: list = []
    seen: list = []
    resolver = _sequenced_resolver([["93.184.216.34"], ["10.0.0.5"]], seen)
    ad = _adapter(environ={}, fetch=_spy_fetch(calls), resolver=resolver)
    text = _error_text(ad.handle_call("read_url", {"url": origin + "/html"}))
    assert "dns_rebound: true" in text
    assert "93.184.216.34" in text and "10.0.0.5" in text
    assert "non-public" in text.lower()  # the new answer is named for what it is
    assert len(calls) == 1  # the fetch happened; its bytes were discarded
    assert seen == ["127.0.0.1", "127.0.0.1"]  # checked before AND after


def test_dns_answer_changing_to_another_public_set_is_still_flagged(origin):
    calls: list = []
    resolver = _sequenced_resolver([["93.184.216.34"], ["93.184.216.35"]], [])
    ad = _adapter(environ={}, fetch=_spy_fetch(calls), resolver=resolver)
    text = _error_text(ad.handle_call("read_url", {"url": origin + "/html"}))
    assert "dns_rebound: true" in text and "retry" in text.lower()
    assert len(calls) == 1


def test_dns_answer_order_and_duplicates_do_not_count_as_a_change(origin):
    resolver = _sequenced_resolver(
        [["93.184.216.34", "93.184.216.35"], ["93.184.216.35", "93.184.216.34"]], []
    )
    ad = _adapter(environ={}, resolver=resolver)
    payload = _payload(ad.handle_call("read_url", {"url": origin + "/html"}))
    assert payload["status"] == 200


def test_stable_dns_answer_is_resolved_twice_per_hop(origin):
    seen: list = []
    resolver = _sequenced_resolver([["93.184.216.34"]], seen)
    ad = _adapter(environ={}, resolver=resolver)
    payload = _payload(ad.handle_call("read_url", {"url": origin + "/hop/2"}))
    assert payload["redirects"] == 2
    assert seen == ["127.0.0.1"] * 6  # 3 hops x (check before + re-check after)


def test_dns_unresolvable_after_the_fetch_is_a_rebound_error(origin):
    resolver = _sequenced_resolver(
        [["93.184.216.34"], socket.gaierror("Name or service not known")], []
    )
    ad = _adapter(environ={}, resolver=resolver)
    text = _error_text(ad.handle_call("read_url", {"url": origin + "/html"}))
    assert "dns_rebound: true" in text and "resolve" in text.lower()


@pytest.mark.parametrize(
    "resolved",
    [
        ["93.184.216.34", "93.184.216.35", "127.0.0.1"],  # private LAST
        ["10.0.0.1", "93.184.216.34"],  # private FIRST
        ["2606:2800:220:1:248:1893:25c8:1946", "fe80::1"],  # v6 link-local
    ],
)
def test_every_resolved_address_is_checked(resolved):
    calls: list = []
    ad = _adapter(environ={}, fetch=_spy_fetch(calls), resolver=lambda _h: resolved)
    text = _error_text(ad.handle_call("read_url", {"url": "http://multi.test/"}))
    assert "private" in text.lower() or "loopback" in text.lower()
    assert calls == []


def test_private_escape_hatch_skips_resolution_and_pinning(origin):
    seen: list = []
    ad = _adapter(environ=ALLOW, resolver=_sequenced_resolver([["1.2.3.4"]], seen))
    payload = _payload(ad.handle_call("read_url", {"url": origin + "/html"}))
    assert payload["status"] == 200 and seen == []
