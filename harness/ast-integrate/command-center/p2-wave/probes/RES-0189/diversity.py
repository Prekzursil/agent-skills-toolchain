"""RES-0189 source-diversity enforcement.

Class distinctness is computed AFTER collapsing shared-origin sources.
Three re-tellings of one vendor blog are one class, even when they wear
four declared-class hats. Padding with restatements is refused.

The 16 class names are reconstructed from catalog citations of the missing
_USER-PROMPTS.md:10681-10717 list. That reconstruction is recorded; it is
not a claim that the missing spec file was read.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# Catalog-reconstructed Phase-2 source classes (16). Spec file is absent.
SOURCE_CLASSES: tuple[str, ...] = (
    "official-docs",
    "source-code",
    "issue-tracker",
    "papers",
    "standards-regulatory",
    "prior-art-patent",
    "vendor-blog",
    "practitioner-report",
    "niche-forum",
    "news-aggregator",
    "video-talk",
    "archival",
    "multilingual",
    "expert-elicitation",
    "owner-decision-log",
    "public-tor",
)

# Distinct CLASSES required by blast-radius / severity.
# K is classes after origin collapse, never raw URL or declared-class count.
K_BY_SEVERITY: dict[str, int] = {
    "P0": 3,  # architectural commitment / load-bearing gate
    "P1": 2,  # contract or schedule
    "P2": 2,  # implementation; a single class is PARTIAL, never CONFIRMED
    "P3": 1,  # note; one independent class is allowed, still unpadded
}

SHERMAN_KENT = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)

# When K is not met, confidence may not exceed this band.
INSUFFICIENT_CONFIDENCE_CAP: dict[str, str] = {
    "P0": "remote",
    "P1": "unlikely",
    "P2": "roughly-even",
    "P3": "likely",
}

PRIMARY_CLASSES = frozenset({"official-docs", "source-code", "standards-regulatory"})
TRACKING_QUERY = re.compile(r"^(utm_|fbclid$|gclid$|mc_)", re.I)

FETCH_TS = "2026-08-24T20:41:00Z"


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    userinfo = ""
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo += ":" + parts.password
        userinfo += "@"
    netloc = userinfo + host
    if parts.port:
        netloc += f":{parts.port}"
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not TRACKING_QUERY.match(k)
    ]
    query = urlencode(query_pairs, doseq=True)
    path = parts.path or ""
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def _content_sha(src: dict[str, Any]) -> str:
    if src.get("content_sha256"):
        return str(src["content_sha256"])
    body = src.get("content")
    if isinstance(body, str) and body:
        return sha256_text(body)
    return ""


def collapse_sources(
    sources: Iterable[dict[str, Any]],
    *,
    use_graph: bool = True,
    use_content: bool = True,
) -> dict[str, Any]:
    """Collapse sources that share an upstream origin, then count classes.

    Signal 1 (graph): derived_from, upstream_origin, canonical URL.
    Signal 2 (content): identical content sha256, even with no derived_from.

    A restatement that declares a different class still inherits the origin
    root's class. Distinct class count is the number of unique root classes
    after collapse — not unique URLs, not unique declared-class labels.
    """
    srcs = [dict(s) for s in sources]
    by_id = {str(s["id"]): s for s in srcs}
    uf = UnionFind()
    for s in srcs:
        sid = str(s["id"])
        uf.add(sid)
        if use_graph:
            derived = s.get("derived_from")
            if derived:
                uf.union(sid, str(derived))
            origin = s.get("upstream_origin")
            if origin:
                uf.union(sid, "origin:" + str(origin).strip().lower())
            curl = canonical_url(str(s.get("url") or ""))
            if curl:
                uf.union(sid, "url:" + curl)
        if use_content:
            digest = _content_sha(s)
            if digest:
                uf.union(sid, "sha:" + digest)

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in srcs:
        groups[uf.find(str(s["id"]))].append(s)

    origin_groups = []
    classes: list[str] = []
    for root_key, members in sorted(groups.items(), key=lambda kv: kv[0]):
        real = [m for m in members if str(m["id"]) in by_id]
        if not real:
            continue
        root = _pick_root(real)
        cls = str(root.get("declared_class") or "unknown")
        classes.append(cls)
        origin_groups.append(
            {
                "origin_id": str(root["id"]),
                "origin_url": canonical_url(str(root.get("url") or "")),
                "class": cls,
                "member_ids": sorted(str(m["id"]) for m in real),
                "declared_classes_on_members": sorted(
                    {str(m.get("declared_class") or "unknown") for m in real}
                ),
                "raw_source_count": len(real),
            }
        )

    distinct = sorted(set(classes))
    naive_declared = sorted({str(s.get("declared_class") or "unknown") for s in srcs})
    naive_urls = sorted({canonical_url(str(s.get("url") or "")) for s in srcs if s.get("url")})
    return {
        "raw_source_count": len(srcs),
        "collapsed_origin_count": len(origin_groups),
        "distinct_class_count": len(distinct),
        "distinct_classes": distinct,
        "origin_groups": origin_groups,
        "naive_declared_class_count": len(naive_declared),
        "naive_declared_classes": naive_declared,
        "naive_url_count": len(naive_urls),
        "collapse_signals": {
            "graph": use_graph,
            "content_sha256": use_content,
        },
    }


def _pick_root(members: list[dict[str, Any]]) -> dict[str, Any]:
    origins = [m for m in members if m.get("is_origin") is True]
    if origins:
        return sorted(origins, key=lambda m: str(m["id"]))[0]
    independent = [m for m in members if not m.get("derived_from")]
    if independent:
        return sorted(independent, key=lambda m: str(m["id"]))[0]
    return sorted(members, key=lambda m: str(m["id"]))[0]


def required_k(severity: str, *, owner_waiver_k: int | None = None) -> int:
    sev = str(severity).upper()
    if sev not in K_BY_SEVERITY:
        raise ValueError(f"unknown severity {severity!r}")
    base = K_BY_SEVERITY[sev]
    if owner_waiver_k is None:
        return base
    if owner_waiver_k < 1 or owner_waiver_k > base:
        raise ValueError("owner waiver may only name a K in [1, default K]")
    return owner_waiver_k


def _confidence_rank(band: str) -> int:
    try:
        return SHERMAN_KENT.index(band)
    except ValueError as exc:
        raise ValueError(f"unknown Sherman-Kent band {band!r}") from exc


def cap_confidence(requested: str | None, cap: str) -> str:
    band = requested if requested in SHERMAN_KENT else cap
    # Higher index = less confident. Cap means "no more confident than cap".
    if _confidence_rank(band) < _confidence_rank(cap):
        return cap
    return band


def evaluate(
    conclusion: dict[str, Any],
    *,
    use_graph: bool = True,
    use_content: bool = True,
) -> dict[str, Any]:
    """Score one conclusion. Never pads classes. Never silently lowers K."""
    severity = str(conclusion.get("severity") or "").upper()
    waiver = conclusion.get("owner_waiver")
    waiver_k = None
    if isinstance(waiver, dict) and waiver.get("named_k") is not None:
        if not waiver.get("owner_id"):
            raise ValueError("owner_waiver requires owner_id; the rule never silently lowers K")
        waiver_k = int(waiver["named_k"])
    k = required_k(severity, owner_waiver_k=waiver_k)
    collapsed = collapse_sources(
        conclusion.get("sources") or [],
        use_graph=use_graph,
        use_content=use_content,
    )
    n_cls = int(collapsed["distinct_class_count"])
    if n_cls <= 0:
        honest = "ZERO-CLASS"
    elif n_cls == 1:
        honest = "SINGLE-CLASS"
    else:
        honest = "MULTI-CLASS"

    satisfied = n_cls >= k
    # P0 additionally needs at least one primary class among collapsed roots.
    missing_primary = False
    if severity == "P0" and satisfied:
        if not (PRIMARY_CLASSES & set(collapsed["distinct_classes"])):
            satisfied = False
            missing_primary = True

    if satisfied:
        status = "SATISFIED"
        if severity == "P3":
            verdict = "CONFIRMED"
            cap = "likely"
        elif severity == "P2":
            verdict = "CONFIRMED"
            cap = "likely"
        elif severity == "P1":
            verdict = "CONFIRMED"
            cap = "likely"
        else:
            verdict = "CONFIRMED"
            cap = "almost-certain"
    else:
        status = "INSUFFICIENT"
        cap = INSUFFICIENT_CONFIDENCE_CAP[severity]
        if n_cls == 0:
            verdict = "NOT-CHECKED"
        elif severity == "P0":
            verdict = "NOT-CHECKED"
        else:
            verdict = "PARTIAL"

    requested = conclusion.get("requested_confidence")
    confidence = cap_confidence(requested if isinstance(requested, str) else cap, cap)

    reason_parts = [
        f"severity={severity} requires K={k} distinct classes after origin collapse",
        f"observed distinct_class_count={n_cls} from raw_source_count={collapsed['raw_source_count']}",
        f"naive declared-class count would have been {collapsed['naive_declared_class_count']}",
    ]
    if missing_primary:
        reason_parts.append("P0 also requires a primary class (official-docs|source-code|standards-regulatory)")
    if honest == "SINGLE-CLASS" and k > 1:
        reason_parts.append(
            "honest output is SINGLE-CLASS; restatements of one origin are not additional classes"
        )

    return {
        "conclusion_id": conclusion.get("id"),
        "severity": severity,
        "required_k": k,
        "owner_waiver_applied": waiver_k is not None,
        "diversity_status": status,
        "honest_output": honest,
        "padding_refused": True,
        "verdict": verdict,
        "confidence": confidence,
        "confidence_cap": cap,
        "missing_primary_class": missing_primary,
        "reason": "; ".join(reason_parts),
        **collapsed,
    }


# --- planted corpora used by the named probes --------------------------------

VENDOR_ORIGIN = (
    "Acme announced Feature X ships in 2.4 with the foo lock held across the bar call.\n"
)
NEWS_RETELL = (
    "According to Acme's blog, Feature X in version 2.4 holds the foo lock across bar.\n"
)
FORUM_RETELL = (
    "Saw the Acme post: 2.4 Feature X, foo lock spanning the bar call. Same claim.\n"
)
PRACTICE_RETELL = (
    "I read Acme's Feature X write-up. Shipping in 2.4; foo lock held across bar.\n"
)
DOCS_INDEPENDENT = (
    "Official reference: Feature X lock protocol, section 4.2, foo mutex around bar().\n"
)
CODE_INDEPENDENT = (
    "void feature_x(void) { lock(&foo); bar(); unlock(&foo); } /* sdk 2.4 */\n"
)
ISSUE_INDEPENDENT = (
    "bugs/4421: Feature X holds foo across bar(); confirmed on the 2.4 tag.\n"
)


def source(
    sid: str,
    url: str,
    declared_class: str,
    *,
    content: str,
    derived_from: str | None = None,
    upstream_origin: str | None = None,
    is_origin: bool = False,
) -> dict[str, Any]:
    return {
        "id": sid,
        "url": url,
        "declared_class": declared_class,
        "content": content,
        "content_sha256": sha256_text(content),
        "derived_from": derived_from,
        "upstream_origin": upstream_origin,
        "is_origin": is_origin,
        "fetch_timestamp": FETCH_TS,
    }


def corpus_four_retellings_of_one_vendor_post() -> dict[str, Any]:
    """Negative control: four sources, one origin. Must report ONE class."""
    origin_token = "acme-feature-x-blog-2026-08-01"
    sources = [
        source(
            "s-vendor",
            "https://acme.example/blog/feature-x?utm_source=rss",
            "vendor-blog",
            content=VENDOR_ORIGIN,
            upstream_origin=origin_token,
            is_origin=True,
        ),
        source(
            "s-news",
            "https://news.example/acme-ships-feature-x",
            "news-aggregator",
            content=NEWS_RETELL,
            derived_from="s-vendor",
            upstream_origin=origin_token,
        ),
        source(
            "s-forum",
            "https://forum.example/t/acme-feature-x/99",
            "niche-forum",
            content=FORUM_RETELL,
            derived_from="s-vendor",
            upstream_origin=origin_token,
        ),
        source(
            "s-practice",
            "https://medium.example/@dev/i-tried-feature-x",
            "practitioner-report",
            content=PRACTICE_RETELL,
            derived_from="s-vendor",
            upstream_origin=origin_token,
        ),
    ]
    return {
        "id": "RES-0189-NC-four-retellings",
        "severity": "P0",
        "requested_confidence": "almost-certain",
        "sources": sources,
    }


def corpus_byte_identical_mirrors() -> dict[str, Any]:
    """Independent collapse signal: identical bytes, no derived_from."""
    body = VENDOR_ORIGIN
    sources = [
        source("m-a", "https://cdn1.example/mirror/feature-x", "vendor-blog", content=body),
        source("m-b", "https://cdn2.example/cache/feature-x", "news-aggregator", content=body),
        source("m-c", "https://archive.example/id/feature-x", "archival", content=body),
        source("m-d", "https://translate.example/en/feature-x", "multilingual", content=body),
    ]
    return {
        "id": "RES-0189-NC-byte-identical-mirrors",
        "severity": "P1",
        "requested_confidence": "likely",
        "sources": sources,
    }


def corpus_three_independent_classes() -> dict[str, Any]:
    sources = [
        source(
            "t-docs",
            "https://docs.acme.example/feature-x",
            "official-docs",
            content=DOCS_INDEPENDENT,
            upstream_origin="acme-docs-feature-x",
            is_origin=True,
        ),
        source(
            "t-code",
            "https://github.com/acme/sdk/blob/v2.4/lock.c",
            "source-code",
            content=CODE_INDEPENDENT,
            upstream_origin="acme-sdk-lock-c",
            is_origin=True,
        ),
        source(
            "t-issue",
            "https://bugs.acme.example/issues/4421",
            "issue-tracker",
            content=ISSUE_INDEPENDENT,
            upstream_origin="acme-bugs-4421",
            is_origin=True,
        ),
    ]
    return {
        "id": "RES-0189-PC-three-independent",
        "severity": "P0",
        "requested_confidence": "almost-certain",
        "sources": sources,
    }


def corpus_p3_single_independent() -> dict[str, Any]:
    return {
        "id": "RES-0189-P3-one-class",
        "severity": "P3",
        "requested_confidence": "almost-certain",
        "sources": [
            source(
                "n-docs",
                "https://docs.acme.example/notes/x",
                "official-docs",
                content=DOCS_INDEPENDENT,
                is_origin=True,
            )
        ],
    }


def write_fixture_bodies() -> dict[str, str]:
    """Persist planted bodies so lineage sha256 is of on-disk bytes."""
    FIXTURES.mkdir(parents=True, exist_ok=True)
    mapping = {
        "vendor-post-origin.txt": VENDOR_ORIGIN,
        "restatement-news.txt": NEWS_RETELL,
        "restatement-forum.txt": FORUM_RETELL,
        "restatement-practitioner.txt": PRACTICE_RETELL,
        "independent-docs.txt": DOCS_INDEPENDENT,
        "independent-code.txt": CODE_INDEPENDENT,
        "independent-issue.txt": ISSUE_INDEPENDENT,
    }
    out: dict[str, str] = {}
    for name, body in mapping.items():
        path = FIXTURES / name
        path.write_text(body, encoding="utf-8", newline="\n")
        out[name] = sha256_bytes(path.read_bytes())
    return out


def lineage_for(rel_under_probe: str, quote: str, line: int = 1) -> dict[str, Any]:
    path = HERE / rel_under_probe
    raw = path.read_bytes()
    rel = f"command-center/p2-wave/probes/RES-0189/{rel_under_probe.replace(chr(92), '/')}"
    return {
        "resolved_url": f"file://{rel}",
        "fetch_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_bytes(raw),
        "path": rel,
        "line": line,
        "quote": quote[:240],
    }


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"
