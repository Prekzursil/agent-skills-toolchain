#!/usr/bin/env python3
"""Six research artifacts whose a priori quality is known to differ.

Live Phase-2 research JSON is absent on this worktree. These committed
fixtures are the validation corpus. A6 is padded with unresolvable or
mismatched citations. A citation counts only when HTTP 2xx AND the
claimed quote appears in both the claim text and the fetched body.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

APRIORI_BEST_TO_WORST = [
    "A1-gold",
    "A2-coverage-gap",
    "A3-single-source",
    "A4-no-contradiction",
    "A5-orphan-unknown",
    "A6-padded-citations",
]
PADDED_ID = "A6-padded-citations"
LOGICAL_HOST = "res-0170.test"

Q_SHA = "SHA-256 produces a 256-bit message digest."
Q_JSON = "json.dumps accepts sort_keys to canonicalize object key order."
Q_404 = "HTTP 404 Not Found means the origin server did not find a current representation."
Q_HASH = "Cryptographic hash functions are one-way and collision-resistant by design."
Q_ISSUE = "The tracker records a failure when the sentinel maps HTTP 200 onto FAILED."
Q_FIPS = "FIPS 180-4 specifies SHA-256 as a 256-bit digest algorithm."
Q_CL = "The 1.2.0 notes list the sentinel inversion as a known detector defect."
Q_KENT = "Sherman-Kent bands map verbal confidence onto a shared probability vocabulary."
Q_CONTRA_SHA = "DISCONFIRMING-SEARCH-LOG: no sampled page claimed SHA-256 is 128-bit."
Q_CONTRA_JSON = "DISCONFIRMING-SEARCH-LOG: no sampled page denied sort_keys on dumps."
Q_CONTRA_404 = "DISCONFIRMING-SEARCH-LOG: no sampled page treated 404 as success."
Q_EXP_UP = "EXPERIMENT: mount _USER-PROMPTS.md:10683-10700 and diff the 16-class list."
Q_EXP_TTL = "EXPERIMENT: re-fetch the 50-source half-life set after 24h (RES-0006)."


def _src(
    cid: str,
    path: str,
    source_class: str,
    origin: str,
    org: str,
    publisher: str,
    quote: str,
    cites: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": cid,
        "url": f"http://{LOGICAL_HOST}{path}",
        "source_class": source_class,
        "origin_id": origin,
        "organisation": org,
        "publisher": publisher,
        "claimed_quote": quote,
        "cites": list(cites or []),
    }


def _claim(
    cid: str,
    text: str,
    sources: list[dict[str, Any]],
    *,
    load_bearing: bool = True,
    contradiction: dict[str, Any] | None = None,
    include_contradiction_key: bool = True,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": cid,
        "claim": text,
        "load_bearing": load_bearing,
        "sources": deepcopy(sources),
    }
    if contradiction is not None:
        row["contradiction_search"] = deepcopy(contradiction)
    elif include_contradiction_key:
        row["contradiction_search"] = {"query": "", "sources": []}
    return row


def _contra(query: str, sid: str, path: str, quote: str) -> dict[str, Any]:
    return {
        "query": query,
        "sources": [
            _src(
                sid,
                path,
                "official-docs",
                "contra.local",
                "Disconfirming search log",
                "fixture-log",
                quote,
            )
        ],
    }


def _experiment(eid: str, method: str, path: str, quote: str) -> dict[str, Any]:
    return {
        "id": eid,
        "method": method,
        "sources": [
            _src(
                eid + "-log",
                path,
                "official-docs",
                "experiment.local",
                "RES-0170 fixtures",
                "named-experiment-log",
                quote,
            )
        ],
    }


def _unknown(uid: str, text: str, experiment: dict[str, Any] | None) -> dict[str, Any]:
    row: dict[str, Any] = {"id": uid, "unknown": text}
    if experiment is not None:
        row["named_experiment"] = experiment
    return row


def bodies() -> dict[str, dict[str, Any]]:
    ok = {
        "/ok/nist-sha256": Q_SHA,
        "/ok/rfc6234": Q_SHA,
        "/ok/src-sha256": Q_SHA,
        "/ok/cpython-json": Q_JSON,
        "/ok/python-docs-json": Q_JSON,
        "/ok/rfc9110-404": Q_404,
        "/ok/mdn-404": Q_404,
        "/ok/src-404": Q_404,
        "/ok/arxiv-hash": Q_HASH,
        "/ok/gh-issue": Q_ISSUE,
        "/ok/archive-fips": Q_FIPS,
        "/ok/changelog": Q_CL,
        "/ok/blog-kent": Q_KENT,
        "/ok/src-hash": Q_HASH,
        "/ok/src-issue": Q_ISSUE,
        "/ok/src-fips": Q_FIPS,
        "/ok/src-cl": Q_CL,
        "/ok/src-kent": Q_KENT,
        "/ok/docs-hash": Q_HASH,
        "/ok/docs-issue": Q_ISSUE,
        "/ok/docs-fips": Q_FIPS,
        "/ok/docs-cl": Q_CL,
        "/ok/docs-kent": Q_KENT,
        "/ok/contra-sha": Q_CONTRA_SHA,
        "/ok/contra-json": Q_CONTRA_JSON,
        "/ok/contra-404": Q_CONTRA_404,
        "/ok/experiment-user-prompts": Q_EXP_UP,
        "/ok/experiment-ttl": Q_EXP_TTL,
        "/mismatch/padded-1": "Lorem ipsum dolor sit amet, citation theatre only.",
        "/mismatch/padded-2": "Unrelated press-release language that does not contain the claimed quote.",
        "/mismatch/padded-3": "Another 200 OK body that fails the content-match gate.",
    }
    routes = {path: {"status": 200, "body": text + "\n"} for path, text in ok.items()}
    for i in range(1, 13):
        routes[f"/missing/padded-{i}"] = {"status": 404, "body": "not found\n"}
    return routes


def _named_unknowns() -> list[dict[str, Any]]:
    return [
        _unknown(
            "U-USER-PROMPTS-16-CLASS",
            "The byte-exact 16 source classes at _USER-PROMPTS.md:10683-10700 are not on this worktree.",
            _experiment(
                "E-mount-user-prompts",
                "Mount the restore snapshot of _USER-PROMPTS.md and diff the class list.",
                "/ok/experiment-user-prompts",
                Q_EXP_UP,
            ),
        )
    ]


def artifact_a1() -> dict[str, Any]:
    return {
        "id": "A1-gold",
        "title": "High-quality research deliverable (planted gold)",
        "a_priori_rank": 1,
        "claims": [
            _claim(
                "C-SHA256-WIDTH",
                f"{Q_SHA} {Q_CONTRA_SHA}",
                [
                    _src("s-nist", "/ok/nist-sha256", "official-docs", "nist.gov", "NIST", "NIST", Q_SHA),
                    _src("s-rfc6234", "/ok/rfc6234", "standards-regulatory", "ietf.org", "IETF", "RFC Editor", Q_SHA),
                ],
                contradiction=_contra("SHA-256 128-bit digest?", "s-contra-sha", "/ok/contra-sha", Q_CONTRA_SHA),
            ),
            _claim(
                "C-JSON-SORT-KEYS",
                f"{Q_JSON} {Q_CONTRA_JSON}",
                [
                    _src("s-cpython", "/ok/cpython-json", "source-code", "github.com/python/cpython", "Python Software Foundation", "CPython", Q_JSON),
                    _src("s-pydocs", "/ok/python-docs-json", "official-docs", "docs.python.org", "Python Docs", "docs.python.org", Q_JSON),
                ],
                contradiction=_contra("json.dumps has no sort_keys?", "s-contra-json", "/ok/contra-json", Q_CONTRA_JSON),
            ),
            _claim(
                "C-HTTP-404",
                f"{Q_404} {Q_CONTRA_404}",
                [
                    _src("s-rfc9110", "/ok/rfc9110-404", "standards-regulatory", "rfc-editor.org", "RFC Editor", "RFC 9110", Q_404),
                    _src("s-mdn", "/ok/mdn-404", "official-docs", "developer.mozilla.org", "Mozilla", "MDN", Q_404),
                ],
                contradiction=_contra("HTTP 404 means success?", "s-contra-404", "/ok/contra-404", Q_CONTRA_404),
            ),
            _claim(
                "C-SUPPORTING-COVERAGE",
                f"{Q_HASH} {Q_ISSUE} {Q_FIPS} {Q_CL} {Q_KENT}",
                [
                    _src("s-arxiv", "/ok/arxiv-hash", "papers", "arxiv.org", "arXiv", "arXiv.org", Q_HASH),
                    _src("s-gh", "/ok/gh-issue", "issue-tracker", "github.com/issues", "GitHub Issues", "issue tracker", Q_ISSUE),
                    _src("s-arch", "/ok/archive-fips", "archival", "archive.org", "Internet Archive", "archive.org", Q_FIPS),
                    _src("s-cl", "/ok/changelog", "changelog", "release-notes.local", "Release notes", "changelog", Q_CL),
                    _src("s-blog", "/ok/blog-kent", "blog-post", "analyst-blog.example", "Analyst Blog", "blog", Q_KENT),
                ],
                load_bearing=False,
                contradiction=_contra("supporting coverage", "s-contra-sha2", "/ok/contra-sha", Q_CONTRA_SHA),
            ),
        ],
        "unknowns": _named_unknowns(),
    }


def artifact_a2() -> dict[str, Any]:
    """Independence, contradiction, unknowns, resolvability intact; only 2 classes."""
    return {
        "id": "A2-coverage-gap",
        "title": "Independent and resolvable, but only official-docs + source-code",
        "a_priori_rank": 2,
        "claims": [
            _claim(
                "C-SHA256-WIDTH",
                f"{Q_SHA} {Q_CONTRA_SHA}",
                [
                    _src("s-nist", "/ok/nist-sha256", "official-docs", "nist.gov", "NIST", "NIST", Q_SHA),
                    _src("s-src-sha", "/ok/src-sha256", "source-code", "github.com/python/cpython", "Python Software Foundation", "CPython comment", Q_SHA),
                ],
                contradiction=_contra("SHA-256 128-bit?", "s-contra-sha", "/ok/contra-sha", Q_CONTRA_SHA),
            ),
            _claim(
                "C-JSON-SORT-KEYS",
                f"{Q_JSON} {Q_CONTRA_JSON}",
                [
                    _src("s-cpython", "/ok/cpython-json", "source-code", "github.com/python/cpython", "Python Software Foundation", "CPython", Q_JSON),
                    _src("s-pydocs", "/ok/python-docs-json", "official-docs", "docs.python.org", "Python Docs", "docs.python.org", Q_JSON),
                ],
                contradiction=_contra("no sort_keys?", "s-contra-json", "/ok/contra-json", Q_CONTRA_JSON),
            ),
            _claim(
                "C-HTTP-404",
                f"{Q_404} {Q_CONTRA_404}",
                [
                    _src("s-mdn", "/ok/mdn-404", "official-docs", "developer.mozilla.org", "Mozilla", "MDN", Q_404),
                    _src("s-src-404", "/ok/src-404", "source-code", "github.com/python/cpython", "Python Software Foundation", "CPython comment", Q_404),
                ],
                contradiction=_contra("404 means success?", "s-contra-404", "/ok/contra-404", Q_CONTRA_404),
            ),
        ],
        "unknowns": _named_unknowns(),
    }


def artifact_a3() -> dict[str, Any]:
    """Eight classes, every load-bearing claim single-sourced."""
    singles = [
        ("C-SHA", Q_SHA, "s-nist", "/ok/nist-sha256", "official-docs", "nist.gov", "NIST", "NIST"),
        ("C-JSON", Q_JSON, "s-cpython", "/ok/cpython-json", "source-code", "github.com/python/cpython", "Python Software Foundation", "CPython"),
        ("C-404", Q_404, "s-rfc9110", "/ok/rfc9110-404", "standards-regulatory", "rfc-editor.org", "RFC Editor", "RFC 9110"),
        ("C-HASH", Q_HASH, "s-arxiv", "/ok/arxiv-hash", "papers", "arxiv.org", "arXiv", "arXiv.org"),
        ("C-ISSUE", Q_ISSUE, "s-gh", "/ok/gh-issue", "issue-tracker", "github.com/issues", "GitHub Issues", "issue tracker"),
        ("C-FIPS", Q_FIPS, "s-arch", "/ok/archive-fips", "archival", "archive.org", "Internet Archive", "archive.org"),
        ("C-CL", Q_CL, "s-cl", "/ok/changelog", "changelog", "release-notes.local", "Release notes", "changelog"),
        ("C-KENT", Q_KENT, "s-blog", "/ok/blog-kent", "blog-post", "analyst-blog.example", "Analyst Blog", "blog"),
    ]
    claims = []
    for cid, quote, sid, path, cls, origin, org, pub in singles:
        claims.append(
            _claim(
                cid,
                f"{quote} {Q_CONTRA_SHA}",
                [_src(sid, path, cls, origin, org, pub, quote)],
                contradiction=_contra("disconfirm " + cid, "c-" + cid, "/ok/contra-sha", Q_CONTRA_SHA),
            )
        )
    return {
        "id": "A3-single-source",
        "title": "Broad class coverage, no independent second source on any claim",
        "a_priori_rank": 3,
        "claims": claims,
        "unknowns": _named_unknowns(),
    }


def artifact_a4() -> dict[str, Any]:
    """Independent and resolvable; contradiction_search omitted."""
    return {
        "id": "A4-no-contradiction",
        "title": "Independent sources, zero contradiction searches",
        "a_priori_rank": 4,
        "claims": [
            _claim(
                "C-SHA256-WIDTH",
                Q_SHA,
                [
                    _src("s-nist", "/ok/nist-sha256", "official-docs", "nist.gov", "NIST", "NIST", Q_SHA),
                    _src("s-rfc6234", "/ok/rfc6234", "standards-regulatory", "ietf.org", "IETF", "RFC Editor", Q_SHA),
                ],
                include_contradiction_key=False,
            ),
            _claim(
                "C-JSON-SORT-KEYS",
                Q_JSON,
                [
                    _src("s-cpython", "/ok/cpython-json", "source-code", "github.com/python/cpython", "Python Software Foundation", "CPython", Q_JSON),
                    _src("s-pydocs", "/ok/python-docs-json", "official-docs", "docs.python.org", "Python Docs", "docs.python.org", Q_JSON),
                ],
                include_contradiction_key=False,
            ),
            _claim(
                "C-HTTP-404",
                Q_404,
                [
                    _src("s-rfc9110", "/ok/rfc9110-404", "standards-regulatory", "rfc-editor.org", "RFC Editor", "RFC 9110", Q_404),
                    _src("s-mdn", "/ok/mdn-404", "official-docs", "developer.mozilla.org", "Mozilla", "MDN", Q_404),
                ],
                include_contradiction_key=False,
            ),
            _claim(
                "C-SUPPORTING-COVERAGE",
                f"{Q_HASH} {Q_ISSUE} {Q_FIPS} {Q_CL}",
                [
                    _src("s-arxiv", "/ok/arxiv-hash", "papers", "arxiv.org", "arXiv", "arXiv.org", Q_HASH),
                    _src("s-gh", "/ok/gh-issue", "issue-tracker", "github.com/issues", "GitHub Issues", "issue tracker", Q_ISSUE),
                    _src("s-arch", "/ok/archive-fips", "archival", "archive.org", "Internet Archive", "archive.org", Q_FIPS),
                    _src("s-cl", "/ok/changelog", "changelog", "release-notes.local", "Release notes", "changelog", Q_CL),
                ],
                load_bearing=False,
                include_contradiction_key=False,
            ),
        ],
        "unknowns": _named_unknowns(),
    }


def artifact_a5() -> dict[str, Any]:
    """Unknowns present without named experiments."""
    return {
        "id": "A5-orphan-unknown",
        "title": "Resolvable claims, unresolved unknowns with no named experiment",
        "a_priori_rank": 5,
        "claims": [
            _claim(
                "C-SHA256-WIDTH",
                f"{Q_SHA} {Q_CONTRA_SHA}",
                [
                    _src("s-nist", "/ok/nist-sha256", "official-docs", "nist.gov", "NIST", "NIST", Q_SHA),
                    _src("s-rfc6234", "/ok/rfc6234", "standards-regulatory", "ietf.org", "IETF", "RFC Editor", Q_SHA),
                ],
                contradiction=_contra("SHA-256 128-bit?", "s-contra-sha", "/ok/contra-sha", Q_CONTRA_SHA),
            ),
            _claim(
                "C-JSON-SORT-KEYS",
                f"{Q_JSON} {Q_CONTRA_JSON}",
                [
                    _src("s-cpython", "/ok/cpython-json", "source-code", "github.com/python/cpython", "Python Software Foundation", "CPython", Q_JSON),
                ],
                contradiction=_contra("no sort_keys?", "s-contra-json", "/ok/contra-json", Q_CONTRA_JSON),
            ),
        ],
        "unknowns": [
            _unknown(
                "U-ORPHAN-1",
                "What is the measured per-class TTL?",
                None,
            ),
            _unknown(
                "U-ORPHAN-2",
                "Which of the 12 research modes did RES-0001..RES-0127 exercise?",
                None,
            ),
        ],
    }


def artifact_a6() -> dict[str, Any]:
    """Citation-shaped padding: 404s, quote mismatches, circular cites."""
    padded_sources = []
    for i in range(1, 13):
        padded_sources.append(
            _src(
                f"s-pad-{i}",
                f"/missing/padded-{i}",
                "official-docs",
                f"pad-origin-{i}.example",
                f"Pad Org {i}",
                f"Pad Publisher {i}",
                Q_SHA,
            )
        )
    mismatches = [
        _src("s-mis-1", "/mismatch/padded-1", "papers", "pad-journal.example", "Pad Journal", "Pad Journal", Q_SHA),
        _src("s-mis-2", "/mismatch/padded-2", "blog-post", "pad-blog.example", "Pad Blog", "Pad Blog", Q_JSON),
        _src("s-mis-3", "/mismatch/padded-3", "wikipedia-secondary", "pad-wiki.example", "Pad Wiki", "Pad Wiki", Q_404),
    ]
    # Circular pair: two URLs, second cites first, both 404.
    circ_a = _src("s-circ-a", "/missing/padded-1", "official-docs", "nist.gov", "NIST", "NIST", Q_SHA)
    circ_b = _src(
        "s-circ-b",
        "/missing/padded-2",
        "standards-regulatory",
        "ietf.org",
        "IETF",
        "RFC Editor",
        Q_SHA,
        cites=["nist.gov"],
    )
    return {
        "id": "A6-padded-citations",
        "title": "Padded with unresolvable and mismatched citations (negative control)",
        "a_priori_rank": 6,
        "planted_defect": "unresolvable-or-mismatched-citations",
        "claims": [
            _claim(
                "C-SHA256-WIDTH",
                f"{Q_SHA} {Q_CONTRA_SHA}",
                [circ_a, circ_b] + padded_sources[:4],
                contradiction={
                    "query": "SHA-256 128-bit?",
                    "sources": padded_sources[4:6],
                },
            ),
            _claim(
                "C-JSON-SORT-KEYS",
                f"{Q_JSON} {Q_CONTRA_JSON}",
                mismatches + padded_sources[6:8],
                contradiction={
                    "query": "no sort_keys?",
                    "sources": padded_sources[8:10],
                },
            ),
            _claim(
                "C-HTTP-404",
                f"{Q_404} {Q_CONTRA_404}",
                padded_sources[10:12],
                contradiction={
                    "query": "404 means success?",
                    "sources": padded_sources[:2],
                },
            ),
        ],
        "unknowns": [
            _unknown(
                "U-PADDED",
                "Unknowns dressed with a fake experiment URL.",
                {
                    "id": "E-fake",
                    "method": "looks like an experiment",
                    "sources": padded_sources[:1],
                },
            )
        ],
    }


def artifacts() -> list[dict[str, Any]]:
    return [
        artifact_a1(),
        artifact_a2(),
        artifact_a3(),
        artifact_a4(),
        artifact_a5(),
        artifact_a6(),
    ]


def filename(art: dict[str, Any]) -> str:
    return f"{art['id']}.json"


def relpath(art: dict[str, Any]) -> str:
    return f"command-center/p2-wave/probes/RES-0170/fixtures/{filename(art)}"


def ensure_on_disk() -> list[Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for art in artifacts():
        path = FIX / filename(art)
        path.write_text(json.dumps(art, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


def load_from_disk() -> list[dict[str, Any]]:
    ensure_on_disk()
    out: list[dict[str, Any]] = []
    for art in artifacts():
        path = FIX / filename(art)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if loaded.get("id") != art["id"]:
            raise ValueError(f"fixture id mismatch {path}")
        out.append(loaded)
    return out
