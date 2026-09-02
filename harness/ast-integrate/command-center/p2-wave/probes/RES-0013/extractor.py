"""Version-indexed breaking/silent-behavior extractor for plugin/skill/hook/MCP.

The definition in DEFINITION is applied BEFORE any count is taken. A probe that
reports a live count without first firing on the seeded known-present fixture
measures nothing.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP = HERE / "snapshots"
REL = SNAP / "releases"
SEED_ID = "SEED-BC-LEGACY-HOOK-DIR"
SEED_MARKER = "SEED-BC-LEGACY-HOOK-DIR"

HEADING_RE = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s*$")
BULLET_RE = re.compile(r"^-\s+(.*)$")

SURFACE_RE = re.compile(
    r"(?i)\b("
    r"plugin|plugins|skill|skills|hook|hooks|mcp|"
    r"marketplace|headershelper|pluginconfigs|user_config|"
    r"skill\.md|plugin\.json|hooks\.json|mcp\.json|"
    r"pretooluse|posttooluse|posttoolusefailure|"
    r"sessionstart|subagentstart|"
    r"enabledplugins|disabledmcpservers|mcpsearch|"
    r"plugin-dir|reload-plugins"
    r")\b"
)

# Applied after surface match. Published before counting.
CHANGE_RE = re.compile(
    r"(?i)("
    r"breaking change|"
    r"\bis now rejected\b|"
    r"\bare no longer\b|"
    r"\bis no longer\b|"
    r"\bno longer (?:read|shadow|runs?|honor|honou?red|fired|available)\b|"
    r"\bcan no longer\b|"
    r"\bremoved ability\b|"
    r"\bpreviously (?:mcp-only|a no-op)\b|"
    r"\bnow require\b|"
    r"\bonly accept one\b|"
    r"\bby default\b|"
    r"\binstead of always requiring\b|"
    r"\binstead of \"resume\"\b|"
    r"^\s*changed\b|"
    r"^\s*removed\b|"
    r"^\s*deprecated\b"
    r")"
)

FIX_START_RE = re.compile(r"(?i)^(fixed|fix|improved|added)\b")

SURFACE_MAP = (
    ("mcp", ("mcp", "headershelper", "disabledmcpservers", "mcpsearch", "mcp.json")),
    ("hook", ("hook", "pretooluse", "posttooluse", "sessionstart", "subagentstart")),
    ("skill", ("skill", "skill.md")),
    ("plugin", ("plugin", "marketplace", "pluginconfigs", "user_config", "plugin.json", "enabledplugins", "plugin-dir", "reload-plugins")),
)

DEFINITION = (
    "A changelog bullet is a plugin/skill/hook/MCP breaking or silently-"
    "behaviour-changing modification when (1) it sits under a ## X.Y.Z "
    "heading, (2) it matches SURFACE_RE, (3) it does not start with "
    "Fixed/Fix/Improved/Added, and (4) it matches CHANGE_RE (Breaking change, "
    "Removed, Changed, no longer, is now rejected, previously MCP-only, now "
    "require, by default, only accept one). This definition is applied before "
    "any count is taken. Additive 'Added a new hook event' bullets are out of "
    "scope. Unversioned claims are defects, not findings."
)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return digest_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def norm(text: str) -> str:
    t = text.replace("`", "").replace("*", "").replace("_", " ")
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def surfaces_of(text: str) -> list[str]:
    low = text.lower()
    hits: list[str] = []
    for name, tokens in SURFACE_MAP:
        if any(tok in low for tok in tokens):
            hits.append(name)
    if not hits and SURFACE_RE.search(text):
        hits.append("plugin")
    if len(hits) > 1:
        return ["mixed"]
    return hits or ["plugin"]


def is_in_scope(bullet: str) -> bool:
    if not SURFACE_RE.search(bullet):
        return False
    if FIX_START_RE.match(bullet.strip()):
        return False
    return bool(CHANGE_RE.search(bullet))


def parse_changelog(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    version: str | None = None
    line_no = 0
    for raw in text.splitlines():
        line_no += 1
        hm = HEADING_RE.match(raw)
        if hm:
            version = hm.group(1)
            continue
        bm = BULLET_RE.match(raw)
        if not bm or version is None:
            continue
        bullet = bm.group(1).strip()
        if not is_in_scope(bullet):
            continue
        surf = surfaces_of(bullet)[0]
        rid = f"BC-{version}-{line_no}"
        if SEED_MARKER in bullet:
            rid = SEED_ID
        rows.append(
            {
                "id": rid,
                "version": version,
                "introduced_in": version,
                "fixed_in": None,
                "surface": surf,
                "changelog_excerpt": bullet,
                "changelog_line": line_no,
                "seeded": SEED_MARKER in bullet,
            }
        )
    return rows


def load_release_bodies() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not REL.is_dir():
        return out
    for path in sorted(REL.glob("v*.slim.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        tag = str(doc.get("tag_name") or path.stem.replace(".slim", ""))
        ver = tag.lstrip("v")
        body = str(doc.get("body") or "")
        if not body.strip():
            continue
        sha, nbytes = digest_file(path)
        out[ver] = {
            "tag": tag,
            "path": str(path.relative_to(REPO)).replace("\\", "/"),
            "html_url": doc.get("html_url"),
            "published_at": doc.get("published_at"),
            "body": body,
            "sha256": sha,
            "bytes": nbytes,
        }
    return out


def load_feed() -> dict[str, Any] | None:
    path = SNAP / "feed.xml"
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    sha, nbytes = digest_file(path)
    return {
        "path": str(path.relative_to(REPO)).replace("\\", "/"),
        "text": path.read_text(encoding="utf-8", errors="replace"),
        "sha256": sha,
        "bytes": nbytes,
    }


def needle_of(excerpt: str) -> str:
    n = norm(excerpt)
    if len(n) <= 96:
        return n
    return n[:96]


def corroborate(row: dict[str, Any], releases: dict[str, dict[str, Any]], feed: dict[str, Any] | None) -> dict[str, Any]:
    needle = needle_of(row["changelog_excerpt"])
    rails: list[dict[str, Any]] = []
    rel = releases.get(row["version"])
    if rel and needle and needle in norm(rel["body"]):
        rails.append(
            {
                "kind": "github-release-body",
                "path": rel["path"],
                "url": rel.get("html_url"),
                "published_at": rel.get("published_at"),
                "sha256": rel["sha256"],
            }
        )
    if feed and needle and needle in norm(feed["text"]):
        rails.append(
            {
                "kind": "rss-feed.xml",
                "path": feed["path"],
                "sha256": feed["sha256"],
            }
        )
    row = dict(row)
    row["corroborated"] = len(rails) >= 1
    row["second_artifact"] = rails[0] if rails else None
    row["corroboration_rails"] = rails
    row["needle"] = needle
    return row


def extract_from_text(text: str, *, with_live_seconds: bool = True) -> dict[str, Any]:
    rows = parse_changelog(text)
    releases = load_release_bodies() if with_live_seconds else {}
    feed = load_feed() if with_live_seconds else None
    out = [corroborate(r, releases, feed) for r in rows]
    return {
        "definition": DEFINITION,
        "rows": out,
        "row_count": len(out),
        "corroborated_count": sum(1 for r in out if r["corroborated"]),
        "seeded_found": any(r.get("seeded") for r in out),
    }


def extract_path(path: Path, *, with_live_seconds: bool = True) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    result = extract_from_text(text, with_live_seconds=with_live_seconds)
    sha, nbytes = digest_file(path)
    result["source"] = {
        "path": _rel(path),
        "sha256": sha,
        "bytes": nbytes,
    }
    return result


def live_extract() -> dict[str, Any]:
    return extract_path(SNAP / "CHANGELOG.md", with_live_seconds=True)


def registry_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain rows live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("register"), list):
        return report
    return doc
