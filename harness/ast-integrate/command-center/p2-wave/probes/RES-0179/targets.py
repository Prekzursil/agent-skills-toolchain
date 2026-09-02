"""Frozen exemplar URLs per reconstructed spec source class.

The 16 class names are reconstructed from WORK-UNIT-CATALOG.json citations of
_USER-PROMPTS.md:10683-10700 (file absent on this worktree). Each restriction
row is settled by a live fetch, not by an unread policy page.
"""
from __future__ import annotations

CONTROL_URL = "https://www.rfc-editor.org/rfc/rfc2119.txt"
NEGATIVE_CONTROL_URL = (
    "https://www.rfc-editor.org/rfc/this-rfc-does-not-exist-res0179.txt"
)
GEO_BLOCK_URL = (
    "https://open.live.bbc.co.uk/mediaselector/6/select/version/2.0/"
    "mediaset/pc/vpid/bbc_one_hd/format/json"
)
EGRESS_URLS = (
    "https://cloudflare.com/cdn-cgi/trace",
    "https://ipinfo.io/json",
)

# public-tor: clearnet DNS/TCP attempt only. No Tor client, no .onion retrieval.
ONION_URL = "http://duckduckgogg42xjoc72x3sjasowoarfglgo7fq5czbqvtioqls.onion/"

SOURCE_CLASS_TARGETS: list[dict] = [
    {
        "source_class": "standards",
        "spec_anchor": "_USER-PROMPTS.md:10689",
        "url": CONTROL_URL,
        "role": "class-exemplar+detector-control",
        "max_bytes": 8192,
    },
    {
        "source_class": "official-docs",
        "spec_anchor": "_USER-PROMPTS.md:10683-10700",
        "url": "https://docs.python.org/3/",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "source-code",
        "spec_anchor": "_USER-PROMPTS.md:10688",
        "url": "https://raw.githubusercontent.com/python/cpython/main/README.rst",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "papers",
        "spec_anchor": "_USER-PROMPTS.md:10683-10700",
        "url": "https://arxiv.org/abs/1706.03762",
        "role": "class-exemplar-open",
        "max_bytes": 16384,
    },
    {
        "source_class": "papers",
        "spec_anchor": "_USER-PROMPTS.md:10683-10700",
        "url": "https://www.nature.com/articles/nature14539",
        "role": "paywall-candidate",
        "max_bytes": 262144,
    },
    {
        "source_class": "papers",
        "spec_anchor": "_USER-PROMPTS.md:10683-10700",
        "url": "https://ieeexplore.ieee.org/document/727498",
        "role": "waf-candidate",
        "max_bytes": 8192,
    },
    {
        "source_class": "forums",
        "spec_anchor": "_USER-PROMPTS.md:10683-10700",
        "url": (
            "https://stackoverflow.com/questions/231767/"
            "what-does-the-yield-keyword-do-in-python"
        ),
        "role": "waf-candidate",
        "max_bytes": 8192,
    },
    {
        "source_class": "archival",
        "spec_anchor": "_USER-PROMPTS.md:10696-10699",
        "url": "https://web.archive.org/web/19970101000000/http://www.google.com/",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "issue-trackers",
        "spec_anchor": "_USER-PROMPTS.md:10687",
        "url": "https://github.com/python/cpython/issues",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "engineering-blogs",
        "spec_anchor": "_USER-PROMPTS.md:10694",
        "url": "https://blog.cloudflare.com/",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "changelogs-release-notes",
        "spec_anchor": "_USER-PROMPTS.md:10686",
        "url": "https://github.com/python/cpython/releases",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "niche-communities",
        "spec_anchor": "_USER-PROMPTS.md:10696",
        "url": "https://news.ycombinator.com/",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "multilingual",
        "spec_anchor": "_USER-PROMPTS.md:10696-10699",
        "url": "https://ja.wikipedia.org/wiki/Python",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "transcripts",
        "spec_anchor": "_USER-PROMPTS.md:10683-10700",
        "url": "https://www.youtube.com/robots.txt",
        "role": "robots-policy",
        "max_bytes": 8192,
    },
    {
        "source_class": "patents",
        "spec_anchor": "_USER-PROMPTS.md:10683-10700",
        "url": "https://patents.google.com/",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "package-registries",
        "spec_anchor": "_USER-PROMPTS.md:10683-10700",
        "url": "https://pypi.org/pypi/pip/json",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "vendor-docs",
        "spec_anchor": "_USER-PROMPTS.md:10683-10700",
        "url": "https://docs.github.com/en/get-started",
        "role": "class-exemplar",
        "max_bytes": 16384,
    },
    {
        "source_class": "public-tor",
        "spec_anchor": "_USER-PROMPTS.md:10699",
        "url": ONION_URL,
        "role": "legal-and-technical-refusal",
        "max_bytes": 1024,
        "timeout": 8.0,
    },
]

BARRIER_TARGETS: list[dict] = [
    {
        "id": "geo-bbc-mediaselector",
        "url": GEO_BLOCK_URL,
        "expect_kind": "geo-blocked",
        "max_bytes": 4096,
    },
    {
        "id": "geo-peacock-unavailable",
        "url": "https://www.peacocktv.com/",
        "expect_kind": "geo-blocked",
        "max_bytes": 32768,
    },
    {
        "id": "paywall-nature",
        "url": "https://www.nature.com/articles/nature14539",
        "expect_kind": "paywalled",
        "max_bytes": 262144,
    },
    {
        "id": "waf-ft",
        "url": "https://www.ft.com/",
        "expect_kind": "waf-or-bot-challenge",
        "max_bytes": 16384,
    },
    {
        "id": "waf-wsj",
        "url": "https://www.wsj.com/",
        "expect_kind": "waf-or-bot-challenge",
        "max_bytes": 8192,
    },
    {
        "id": "robots-linkedin",
        "url": "https://www.linkedin.com/robots.txt",
        "expect_kind": "robots-excluded",
        "max_bytes": 262144,
    },
    {
        "id": "robots-github",
        "url": "https://github.com/robots.txt",
        "expect_kind": "robots-path-exclusions",
        "max_bytes": 32768,
    },
    {
        "id": "legal-nyt-tdm-notice",
        "url": "https://www.nytimes.com/robots.txt",
        "expect_kind": "legally-restricted",
        "max_bytes": 16384,
    },
    {
        "id": "reachable-govuk",
        "url": "https://www.gov.uk/",
        "expect_kind": "reachable",
        "max_bytes": 16384,
    },
]
