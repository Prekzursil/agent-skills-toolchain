#!/usr/bin/env python3
"""Standing watchlist: event-driven recheck, not a poller.

Wake signals by source class (load-bearing):
  html-docs     canonical content hash (ads/time stripped)
  plain-spec    normalized text hash
  feed          entry-id set
  release       release-tag set
  registry      published version (plus file digest set when present)
  vcs           commit/entry-id set

Cheap prechecks (ETag, Last-Modified) may skip a body fetch on 304.
They do NOT wake by themselves for html/feed: a watcher that wakes on
Date/Last-Modified/ad-markup/lastBuildDate is a poller.

A wake enqueues claim revalidation for citations of that source only.
"""
from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree as ET

SKIP_TAGS = frozenset(
    {"script", "style", "noscript", "iframe", "template", "svg", "ins"}
)
AD_HINTS = (
    "adsbygoogle",
    "advertisement",
    "ad-slot",
    "adslot",
    "sponsored",
    "cookie-banner",
    "cookiebanner",
)
TIME_TAGS = frozenset({"time"})


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def localname(tag: str) -> str:
    return tag.split("}", 1)[-1].lower() if "}" in tag else tag.lower()


def _attr_blob(attrs: list[tuple[str, str | None]]) -> str:
    parts = []
    for k, v in attrs:
        kk = (k or "").lower()
        vv = (v or "").lower()
        parts.append(kk + "=" + vv)
    return " ".join(parts)


def looks_like_ad(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
    blob = (tag + " " + _attr_blob(attrs)).lower()
    return any(h in blob for h in AD_HINTS)


class _CanonHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if self.skip_depth:
            self.skip_depth += 1
            return
        if t in SKIP_TAGS or t in TIME_TAGS or looks_like_ad(t, attrs):
            self.skip_depth = 1
            return
        href = ""
        for k, v in attrs:
            if (k or "").lower() in {"href", "src"} and v:
                href = v.strip()
                break
        if href and not href.startswith(("javascript:", "data:")):
            self.chunks.append(" " + href + " ")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            self.skip_depth = max(0, self.skip_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.chunks.append(text)


def scrub_generated_stamps(text: str) -> str:
    """Drop clock/render stamps so timestamp-only edits are not wakes."""
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?", " ", text)
    text = re.sub(
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{1,2} \w{3} \d{4} \d{2}:\d{2}:\d{2} GMT",
        " ",
        text,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", text).strip()


def canonical_html_parser(raw: bytes) -> str:
    parser = _CanonHTML()
    try:
        parser.feed(raw.decode("utf-8", errors="replace"))
        parser.close()
    except Exception:
        return scrub_generated_stamps(raw.decode("utf-8", errors="replace"))
    return scrub_generated_stamps(" ".join(parser.chunks))


def canonical_html_regex(raw: bytes) -> str:
    """Second, mechanically different HTML stripper (regex, not html.parser)."""
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<(script|style|noscript|iframe|template|svg|ins)\b[\s\S]*?</\1>", " ", s)
    s = re.sub(r"(?is)<time\b[\s\S]*?</time>", " ", s)
    s = re.sub(r"(?is)<!--.*?-->", " ", s)
    s = re.sub(
        r'(?is)<[^>]*(adsbygoogle|advertisement|ad-slot|adslot|sponsored)[^>]*>[\s\S]*?</[^>]+>',
        " ",
        s,
    )
    s = re.sub(r"(?is)<[^>]+>", " ", s)
    return scrub_generated_stamps(s)


def canonical_text(raw: bytes) -> str:
    s = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"(?m)^\[generated-at:.*?\]\s*$", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip() + "\n"


def _iter_xml(raw: bytes) -> ET.Element | None:
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        return None


def feed_entry_ids(raw: bytes) -> list[str]:
    root = _iter_xml(raw)
    if root is None:
        return []
    ids: list[str] = []
    for el in root.iter():
        name = localname(el.tag)
        if name in {"entry", "item"}:
            found = ""
            for child in list(el):
                cn = localname(child.tag)
                if cn in {"id", "guid"} and (child.text or "").strip():
                    found = child.text.strip()
                    break
            if not found:
                for child in list(el):
                    if localname(child.tag) == "link":
                        href = child.attrib.get("href") or (child.text or "").strip()
                        if href:
                            found = href
                            break
            if found:
                ids.append(found)
    return sorted(set(ids))


def feed_channel_stamp(raw: bytes) -> str:
    root = _iter_xml(raw)
    if root is None:
        return ""
    nodes = [root]
    if localname(root.tag) == "rss":
        nodes = [c for c in list(root) if localname(c.tag) == "channel"] or [root]
    for node in nodes:
        for child in list(node):
            if localname(child.tag) in {"updated", "lastbuilddate", "pubdate", "modified"}:
                return (child.text or "").strip()
    return ""


def release_tags_from_feed(raw: bytes) -> list[str]:
    """GitHub releases.atom titles/ids are tags or tag URLs."""
    ids = feed_entry_ids(raw)
    tags: list[str] = []
    for i in ids:
        # .../releases/tag/X or .../releases/X
        m = re.search(r"/releases/tag/([^/#?]+)", i)
        if m:
            tags.append(m.group(1))
            continue
        m = re.search(r"/releases/([^/#?]+)$", i)
        if m and m.group(1) not in {"latest", "download"}:
            tags.append(m.group(1))
            continue
        tags.append(i)
    return sorted(set(tags))


def registry_version(raw: bytes, content_type: str) -> str:
    try:
        doc = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return ""
    if not isinstance(doc, dict):
        return ""
    info = doc.get("info")
    if isinstance(info, dict) and isinstance(info.get("version"), str):
        return info["version"]
    if isinstance(doc.get("version"), str):
        return doc["version"]
    crate = doc.get("crate")
    if isinstance(crate, dict) and isinstance(crate.get("max_version"), str):
        return crate["max_version"]
    if isinstance(doc.get("max_stable_version"), str):
        return str(doc["max_stable_version"])
    return ""


def registry_file_digests(raw: bytes) -> list[str]:
    try:
        doc = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    if not isinstance(doc, dict):
        return []
    urls = doc.get("urls")
    out: list[str] = []
    if isinstance(urls, list):
        for u in urls:
            if not isinstance(u, dict):
                continue
            dig = u.get("digests")
            if isinstance(dig, dict) and isinstance(dig.get("sha256"), str):
                out.append(dig["sha256"].lower())
    versions = doc.get("versions")
    if isinstance(versions, list):
        for v in versions[:15]:
            if isinstance(v, dict) and isinstance(v.get("num"), str):
                out.append("ver:" + v["num"])
    return sorted(set(out))


def classify(url: str, content_type: str, raw: bytes) -> str:
    u = url.lower()
    ct = (content_type or "").lower()
    if "releases.atom" in u or "/releases/" in u and u.endswith(".atom"):
        return "release"
    if u.endswith(".atom") or "/commits/" in u and "atom" in u:
        return "vcs" if "/commits/" in u else "feed"
    if "rss" in u or "atom" in u or "xml" in ct or "atom+xml" in ct or "rss+xml" in ct:
        if raw[:200].lstrip().startswith(b"<?xml") or b"<feed" in raw[:400] or b"<rss" in raw[:400]:
            return "feed"
    if "/pypi/" in u and u.endswith("/json"):
        return "registry"
    if "registry.npmjs.org" in u or "crates.io/api" in u:
        return "registry"
    if "text/plain" in ct or u.endswith(".txt") or u.endswith(".rst"):
        return "plain-spec"
    if "json" in ct or raw[:1] in (b"{", b"["):
        try:
            json.loads(raw.decode("utf-8", errors="replace"))
            if registry_version(raw, ct):
                return "registry"
        except json.JSONDecodeError:
            pass
    return "html-docs"


def fingerprint(source_class: str, raw: bytes, headers: dict[str, str], url: str) -> dict[str, Any]:
    ct = headers.get("content-type") or headers.get("Content-Type") or ""
    etag = headers.get("etag") or headers.get("ETag") or ""
    last_mod = headers.get("last-modified") or headers.get("Last-Modified") or ""
    date_h = headers.get("date") or headers.get("Date") or ""
    raw_sha = sha256_bytes(raw)
    fp: dict[str, Any] = {
        "source_class": source_class,
        "url": url,
        "raw_sha256": raw_sha,
        "etag": etag,
        "last_modified": last_mod,
        "date_header": date_h,
        "bytes": len(raw),
        "wake_value": "",
        "wake_signal": "",
        "parser_canonical_sha256": "",
        "regex_canonical_sha256": "",
        "entry_ids": [],
        "release_tags": [],
        "registry_version": "",
        "file_digests": [],
        "channel_stamp": "",
    }
    if source_class == "html-docs":
        p = canonical_html_parser(raw)
        r = canonical_html_regex(raw)
        fp["parser_canonical_sha256"] = sha256_text(p)
        fp["regex_canonical_sha256"] = sha256_text(r)
        fp["wake_value"] = fp["parser_canonical_sha256"]
        fp["wake_signal"] = "content-hash"
    elif source_class == "plain-spec":
        t = canonical_text(raw)
        fp["parser_canonical_sha256"] = sha256_text(t)
        fp["regex_canonical_sha256"] = sha256_text(re.sub(r"\s+", " ", t))
        fp["wake_value"] = fp["parser_canonical_sha256"]
        fp["wake_signal"] = "content-hash"
    elif source_class == "feed":
        ids = feed_entry_ids(raw)
        fp["entry_ids"] = ids
        fp["channel_stamp"] = feed_channel_stamp(raw)
        fp["wake_value"] = sha256_text("\n".join(ids))
        fp["wake_signal"] = "feed-entry"
    elif source_class == "release":
        tags = release_tags_from_feed(raw)
        if not tags:
            tags = feed_entry_ids(raw)
        fp["release_tags"] = tags
        fp["entry_ids"] = feed_entry_ids(raw)
        fp["channel_stamp"] = feed_channel_stamp(raw)
        fp["wake_value"] = sha256_text("\n".join(tags))
        fp["wake_signal"] = "release-tag"
    elif source_class == "vcs":
        ids = feed_entry_ids(raw)
        fp["entry_ids"] = ids
        fp["channel_stamp"] = feed_channel_stamp(raw)
        fp["wake_value"] = sha256_text("\n".join(ids))
        fp["wake_signal"] = "release-tag" if False else "feed-entry"
        fp["wake_signal"] = "feed-entry"
    elif source_class == "registry":
        ver = registry_version(raw, ct)
        digs = registry_file_digests(raw)
        fp["registry_version"] = ver
        fp["file_digests"] = digs
        fp["wake_value"] = ver + "|" + sha256_text("\n".join(digs))
        fp["wake_signal"] = "content-hash" if not ver else "release-tag"
        # registry version is the release-tag analogue for packages
        fp["wake_signal"] = "release-tag"
    else:
        fp["wake_value"] = raw_sha
        fp["wake_signal"] = "content-hash"
    return fp


def decide_wake(prev: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    """Watcher wake vs naive poller wake."""
    poller = prev.get("raw_sha256") != curr.get("raw_sha256")
    watcher = prev.get("wake_value") != curr.get("wake_value")
    etag_changed = bool(prev.get("etag") and curr.get("etag") and prev.get("etag") != curr.get("etag"))
    lm_changed = bool(
        prev.get("last_modified")
        and curr.get("last_modified")
        and prev.get("last_modified") != curr.get("last_modified")
    )
    stamp_changed = bool(
        prev.get("channel_stamp")
        and curr.get("channel_stamp")
        and prev.get("channel_stamp") != curr.get("channel_stamp")
    )
    reason = "unchanged"
    if watcher:
        reason = f"wake-signal:{curr.get('wake_signal')}"
    elif poller:
        reason = "raw-bytes-changed-canonical-stable"
    elif etag_changed or lm_changed or stamp_changed:
        reason = "header-or-stamp-only"
    return {
        "watcher_wake": watcher,
        "poller_wake": poller,
        "etag_changed": etag_changed,
        "last_modified_changed": lm_changed,
        "channel_stamp_changed": stamp_changed,
        "reason": reason,
        "prev_wake_value": prev.get("wake_value"),
        "curr_wake_value": curr.get("wake_value"),
    }


# --- both-states fixtures -------------------------------------------------

HTML_BASE = """<!DOCTYPE html>
<html><head><title>Watchlist fixture</title>
<meta name="generated" content="2026-08-01T00:00:00Z">
</head><body>
<h1>Standing recheck</h1>
<p id="lead">The load-bearing paragraph states that ETag alone is not a wake.</p>
<div class="ad-slot"><ins class="adsbygoogle">Buy now @ 2026-08-01T00:00:00Z</ins></div>
<time datetime="2026-08-01T00:00:00Z">updated 2026-08-01</time>
<footer>page rendered at 2026-08-01T00:00:00Z</footer>
</body></html>
"""

HTML_GENUINE = HTML_BASE.replace(
    "The load-bearing paragraph states that ETag alone is not a wake.",
    "The load-bearing paragraph now states that a new claim requires revalidation.",
)

HTML_COSMETIC = """<!DOCTYPE html>
<html><head><title>Watchlist fixture</title>
<meta name="generated" content="2026-08-24T18:00:00Z">
</head><body>
<h1>Standing recheck</h1>
<p id="lead">The load-bearing paragraph states that ETag alone is not a wake.</p>
<div class="ad-slot"><ins class="adsbygoogle">Buy now @ 2026-08-24T18:00:00Z — extra banner</ins></div>
<div class="advertisement">tracker pixel ts=2026-08-24T18:00:00Z</div>
<time datetime="2026-08-24T18:00:00Z">updated 2026-08-24</time>
<footer>page rendered at 2026-08-24T18:00:00Z</footer>
</body></html>
"""

FEED_BASE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>releases</title>
  <updated>2026-08-01T00:00:00Z</updated>
  <entry>
    <id>tag:example.org,2026:v1.0.0</id>
    <title>v1.0.0</title>
    <updated>2026-07-01T00:00:00Z</updated>
    <link href="https://example.org/releases/tag/v1.0.0"/>
  </entry>
</feed>
"""

FEED_GENUINE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>releases</title>
  <updated>2026-08-08T00:00:00Z</updated>
  <entry>
    <id>tag:example.org,2026:v1.1.0</id>
    <title>v1.1.0</title>
    <updated>2026-08-08T00:00:00Z</updated>
    <link href="https://example.org/releases/tag/v1.1.0"/>
  </entry>
  <entry>
    <id>tag:example.org,2026:v1.0.0</id>
    <title>v1.0.0</title>
    <updated>2026-07-01T00:00:00Z</updated>
    <link href="https://example.org/releases/tag/v1.0.0"/>
  </entry>
</feed>
"""

FEED_COSMETIC = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>releases</title>
  <updated>2026-08-24T18:00:00Z</updated>
  <entry>
    <id>tag:example.org,2026:v1.0.0</id>
    <title>v1.0.0</title>
    <updated>2026-07-01T00:00:00Z</updated>
    <link href="https://example.org/releases/tag/v1.0.0"/>
  </entry>
</feed>
"""

REL_BASE = json.dumps(
    [{"tag_name": "v1.0.0", "published_at": "2026-07-01T00:00:00Z"}],
    indent=0,
)
REL_GENUINE = json.dumps(
    [
        {"tag_name": "v1.1.0", "published_at": "2026-08-08T00:00:00Z"},
        {"tag_name": "v1.0.0", "published_at": "2026-07-01T00:00:00Z"},
    ],
    indent=0,
)
REL_COSMETIC = json.dumps(
    [{"tag_name": "v1.0.0", "published_at": "2026-08-24T18:00:00Z"}],
    indent=0,
)


def _fp_html(text: str, etag: str, last_mod: str) -> dict[str, Any]:
    raw = text.encode("utf-8")
    headers = {"ETag": etag, "Last-Modified": last_mod, "Content-Type": "text/html"}
    return fingerprint("html-docs", raw, headers, "https://fixture.local/page")


def _fp_feed(text: str) -> dict[str, Any]:
    raw = text.encode("utf-8")
    headers = {"Content-Type": "application/atom+xml"}
    return fingerprint("feed", raw, headers, "https://fixture.local/feed.atom")


def _fp_release_json(text: str) -> dict[str, Any]:
    """Release-tag set from GitHub-like JSON (fixture only)."""
    raw = text.encode("utf-8")
    doc = json.loads(text)
    tags = sorted({row["tag_name"] for row in doc})
    fp = fingerprint("registry", raw, {"Content-Type": "application/json"}, "https://fixture.local/releases")
    # override: this fixture is a tag set, not a registry version
    fp["source_class"] = "release"
    fp["release_tags"] = tags
    fp["wake_value"] = sha256_text("\n".join(tags))
    fp["wake_signal"] = "release-tag"
    fp["registry_version"] = ""
    return fp


def both_states() -> dict[str, Any]:
    html_base = _fp_html(HTML_BASE, etag='"v1"', last_mod="Sat, 01 Aug 2026 00:00:00 GMT")
    html_gen = _fp_html(HTML_GENUINE, etag='"v2"', last_mod="Sun, 24 Aug 2026 00:00:00 GMT")
    html_cos = _fp_html(HTML_COSMETIC, etag='"v1-ads"', last_mod="Sun, 24 Aug 2026 18:00:00 GMT")
    d_gen = decide_wake(html_base, html_gen)
    d_cos = decide_wake(html_base, html_cos)

    feed_base = _fp_feed(FEED_BASE)
    feed_gen = _fp_feed(FEED_GENUINE)
    feed_cos = _fp_feed(FEED_COSMETIC)
    f_gen = decide_wake(feed_base, feed_gen)
    f_cos = decide_wake(feed_base, feed_cos)

    rel_base = _fp_release_json(REL_BASE)
    rel_gen = _fp_release_json(REL_GENUINE)
    rel_cos = _fp_release_json(REL_COSMETIC)
    r_gen = decide_wake(rel_base, rel_gen)
    r_cos = decide_wake(rel_base, rel_cos)

    # independent regex path on HTML
    regex_base = sha256_text(canonical_html_regex(HTML_BASE.encode()))
    regex_gen = sha256_text(canonical_html_regex(HTML_GENUINE.encode()))
    regex_cos = sha256_text(canonical_html_regex(HTML_COSMETIC.encode()))
    regex_wakes_genuine = regex_base != regex_gen
    regex_silent_cosmetic = regex_base == regex_cos

    parser_silent_cosmetic = html_base["wake_value"] == html_cos["wake_value"]
    parser_wakes_genuine = html_base["wake_value"] != html_gen["wake_value"]

    poller_is_poller = d_gen["poller_wake"] and d_cos["poller_wake"]
    watcher_not_poller = d_gen["watcher_wake"] and (not d_cos["watcher_wake"])

    cases = [
        {
            "id": "html-genuine",
            "plant": "change load-bearing paragraph",
            "watcher_wake": d_gen["watcher_wake"],
            "poller_wake": d_gen["poller_wake"],
            "want_watcher": True,
            "verdict": "PASS" if d_gen["watcher_wake"] else "FAIL",
        },
        {
            "id": "html-cosmetic",
            "plant": "change ad markup, time element, and Last-Modified/ETag",
            "watcher_wake": d_cos["watcher_wake"],
            "poller_wake": d_cos["poller_wake"],
            "want_watcher": False,
            "verdict": "PASS" if not d_cos["watcher_wake"] else "FAIL",
        },
        {
            "id": "feed-genuine",
            "plant": "new atom entry id / release tag",
            "watcher_wake": f_gen["watcher_wake"],
            "poller_wake": f_gen["poller_wake"],
            "want_watcher": True,
            "verdict": "PASS" if f_gen["watcher_wake"] else "FAIL",
        },
        {
            "id": "feed-cosmetic",
            "plant": "channel <updated> / lastBuildDate only",
            "watcher_wake": f_cos["watcher_wake"],
            "poller_wake": f_cos["poller_wake"],
            "want_watcher": False,
            "verdict": "PASS" if not f_cos["watcher_wake"] else "FAIL",
        },
        {
            "id": "release-genuine",
            "plant": "new tag_name in release set",
            "watcher_wake": r_gen["watcher_wake"],
            "poller_wake": r_gen["poller_wake"],
            "want_watcher": True,
            "verdict": "PASS" if r_gen["watcher_wake"] else "FAIL",
        },
        {
            "id": "release-cosmetic",
            "plant": "published_at change, same tag_name",
            "watcher_wake": r_cos["watcher_wake"],
            "poller_wake": r_cos["poller_wake"],
            "want_watcher": False,
            "verdict": "PASS" if not r_cos["watcher_wake"] else "FAIL",
        },
    ]
    all_pass = all(c["verdict"] == "PASS" for c in cases)
    independent_agree = regex_wakes_genuine and regex_silent_cosmetic
    ok = (
        all_pass
        and watcher_not_poller
        and poller_is_poller
        and parser_silent_cosmetic
        and parser_wakes_genuine
        and independent_agree
        and f_cos["channel_stamp_changed"]
        and (not f_cos["watcher_wake"])
    )
    return {
        "pass": ok,
        "cases": cases,
        "watcher_not_poller": watcher_not_poller,
        "poller_wakes_on_both": poller_is_poller,
        "independent_regex_agrees": independent_agree,
        "html_parser_canonical_base": html_base["wake_value"],
        "html_parser_canonical_cosmetic": html_cos["wake_value"],
        "html_parser_canonical_genuine": html_gen["wake_value"],
        "html_regex_canonical_base": regex_base,
        "html_regex_canonical_cosmetic": regex_cos,
        "html_regex_canonical_genuine": regex_gen,
        "feed_cosmetic_stamp_changed": f_cos["channel_stamp_changed"],
        "fixture_html_base_sha256": sha256_text(HTML_BASE),
        "fixture_html_genuine_sha256": sha256_text(HTML_GENUINE),
        "fixture_html_cosmetic_sha256": sha256_text(HTML_COSMETIC),
    }


SIGNALS_BY_CLASS = [
    {
        "source_class": "html-docs",
        "wake_signal": "content-hash of ad/time-stripped canonical body",
        "ignore_signal": "ETag, Last-Modified, Date, ads, <time>, generated-at stamps",
        "cheap_precheck": "If-None-Match / If-Modified-Since (304 skips body; 200 still canonicalizes)",
    },
    {
        "source_class": "plain-spec",
        "wake_signal": "content-hash of newline-normalized text",
        "ignore_signal": "Last-Modified/Date headers; generated-at banner lines",
        "cheap_precheck": "ETag",
    },
    {
        "source_class": "feed",
        "wake_signal": "feed-entry id/guid set",
        "ignore_signal": "channel lastBuildDate / updated without new entry ids",
        "cheap_precheck": "ETag on the feed document",
    },
    {
        "source_class": "release",
        "wake_signal": "release-tag set",
        "ignore_signal": "published_at / html cosmetics for an unchanged tag",
        "cheap_precheck": "ETag on releases.atom or API",
    },
    {
        "source_class": "registry",
        "wake_signal": "published version string plus file digest set",
        "ignore_signal": "last_serial / upload timestamps when version and digests match",
        "cheap_precheck": "ETag on JSON",
    },
    {
        "source_class": "vcs",
        "wake_signal": "commit / entry-id set from the commits atom",
        "ignore_signal": "feed updated stamp without new commit ids",
        "cheap_precheck": "ETag",
    },
]


ON_WAKE = [
    "append WatchEvent {source_id, source_class, wake_signal, prev_wake_value, curr_wake_value, observed_at, body_sha256, etag}",
    "enqueue claim-revalidation only for claims whose lineage cites this source_id",
    "do not refetch the rest of the watchlist (that would be polling everything)",
    "after revalidation, store the new fingerprint as the standing snapshot",
]


if __name__ == "__main__":
    result = both_states()
    print(json.dumps({k: result[k] for k in result if k != "cases"}, indent=1, sort_keys=True))
    print("cases", [(c["id"], c["verdict"]) for c in result["cases"]])
    raise SystemExit(0 if result["pass"] else 1)
