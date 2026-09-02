"""Source-class vocabulary for RES-0185.

Canonical 16-name list is _USER-PROMPTS.md:10683, absent on this worktree.
Names match the reconstruction already shipped in RES-0149 so this map
and that record do not invent two vocabularies.
"""
from __future__ import annotations

from urllib.parse import urlparse

# Locked to RES-0149 SOURCE_CLASS_VOCABULARY.
SOURCE_CLASSES: tuple[str, ...] = (
    "official-docs",
    "source-code",
    "issue-trackers",
    "changelogs-release-notes",
    "standards",
    "papers",
    "engineering-blogs",
    "forums",
    "archival",
    "niche",
    "multilingual",
    "anecdotal",
    "video-talk-transcripts",
    "public-tor",
    "mailing-lists",
    "q-and-a",
)

SOURCE_CLASS_SET = frozenset(SOURCE_CLASSES)

_ALIASES = {
    "official-docs": "official-docs",
    "docs": "official-docs",
    "documentation": "official-docs",
    "source-code": "source-code",
    "code": "source-code",
    "issue-trackers": "issue-trackers",
    "issues": "issue-trackers",
    "changelogs-release-notes": "changelogs-release-notes",
    "changelogs": "changelogs-release-notes",
    "release-notes": "changelogs-release-notes",
    "standards": "standards",
    "papers": "papers",
    "engineering-blogs": "engineering-blogs",
    "blogs": "engineering-blogs",
    "forums": "forums",
    "archival": "archival",
    "niche": "niche",
    "multilingual": "multilingual",
    "anecdotal": "anecdotal",
    "video-talk-transcripts": "video-talk-transcripts",
    "public-tor": "public-tor",
    "mailing-lists": "mailing-lists",
    "q-and-a": "q-and-a",
}


def canonicalize_class(raw: str | None) -> str | None:
    if not raw:
        return None
    key = str(raw).strip().lower().replace("_", "-").replace(" ", "-")
    mapped = _ALIASES.get(key, key)
    if mapped in SOURCE_CLASS_SET:
        return mapped
    return None


def unwrap_archive(url: str) -> str:
    if "web.archive.org/web/" not in url:
        return url
    idx = url.find("/http")
    if idx == -1:
        return url
    inner = url[idx + 1 :]
    if inner.startswith("http"):
        return inner
    return url


def canonical_url(url: str) -> str:
    url = unwrap_archive(url.strip())
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or ""
    if path.endswith("/") and len(path) > 1:
        path = path[:-1]
    scheme = parsed.scheme.lower() or "https"
    return f"{scheme}://{host}{path}"


def classify_url(url: str) -> str | None:
    """Classify a recorded locator. Does not fetch or read the body."""
    raw = (url or "").strip()
    if not raw:
        return None
    inner = unwrap_archive(raw)
    if "web.archive.org" in raw and inner == raw:
        return "archival"
    parsed = urlparse(inner)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (parsed.path or "").lower()
    if host.endswith(".onion"):
        return "public-tor"
    if "arxiv.org" in host:
        return "papers"
    if host in {
        "aclanthology.org",
        "doi.org",
        "dx.doi.org",
        "acm.org",
        "dl.acm.org",
        "neurips.cc",
        "proceedings.neurips.cc",
        "aclweb.org",
    }:
        return "papers"
    if host in {
        "ietf.org",
        "datatracker.ietf.org",
        "rfc-editor.org",
        "w3.org",
        "ieee.org",
        "standards.ieee.org",
        "ieeexplore.ieee.org",
        "iso.org",
        "peps.python.org",
        "states-language.net",
    } or host.endswith(".ietf.org"):
        return "standards"
    if (
        host.startswith("docs.")
        or host in {
            "learn.microsoft.com",
            "kubernetes.io",
            "docs.python.org",
            "docs.github.com",
            "temporal.io",
            "federalreserve.gov",
        }
        or host.endswith(".readthedocs.io")
    ):
        return "official-docs"
    if host in {"stackoverflow.com"} or host.endswith(".stackexchange.com"):
        return "q-and-a"
    if host in {"lists.w3.org", "mail.python.org"}:
        return "mailing-lists"
    if host in {"youtube.com", "youtu.be"}:
        return "video-talk-transcripts"
    if host == "medium.com" or "blog" in host.split("."):
        return "engineering-blogs"
    if host in {"reddit.com"} or "discourse" in host:
        return "forums"
    if host == "github.com":
        if "/issues" in path or "/pull/" in path:
            return "issue-trackers"
        return "source-code"
    if host in {"raw.githubusercontent.com", "api.github.com"}:
        return "source-code"
    if host == "web.archive.org":
        return "archival"
    return None
