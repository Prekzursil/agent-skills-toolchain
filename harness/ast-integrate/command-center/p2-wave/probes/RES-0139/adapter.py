#!/usr/bin/env python3
"""Standards / working-group source adapters for RES-0139.

Each source class has a stable machine-readable extraction path for:
  * a normative requirement (RFC 2119 / BCP 14 keyword + section)
  * discussion-history pointers (rev_history, related documents, commits, Specref)

Probes rehash frozen snapshots. They do not refetch the network.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
SOURCES = FIXTURES / "sources"
MANIFEST = FIXTURES / "fetch-manifest.json"

KEYWORDS = (
    "MUST NOT",
    "SHALL NOT",
    "SHOULD NOT",
    "NOT RECOMMENDED",
    "REQUIRED",
    "RECOMMENDED",
    "MUST",
    "SHALL",
    "SHOULD",
    "OPTIONAL",
    "MAY",
)
KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in KEYWORDS) + r")\b"
)

# Stable extraction routes claimed by this unit.
ADAPTERS = {
    "ietf": {
        "id": "ietf-datatracker",
        "title": "IETF Datatracker + RFC Editor JSON/text",
        "machine_readable": (
            "RFC Editor JSON metadata (https://www.rfc-editor.org/rfc/rfcNNNN.json) "
            "plus Datatracker document JSON "
            "(https://datatracker.ietf.org/doc/rfcNNNN/doc.json and "
            "/api/v1/doc/document/rfcNNNN/) plus the canonical RFC text/xml2rfc. "
            "Normative keywords are extracted from the RFC body; discussion history "
            "is datatracker rev_history plus /api/v1/doc/relateddocument/."
        ),
        "discussion_history": (
            "datatracker rev_history[], relateddocument relationship objects "
            "(contains/updates/obsoletes/refnorm), and mailarchive.ietf.org "
            "(HTTP 403 without session — not used as a load-bearing rail)."
        ),
    },
    "w3c": {
        "id": "w3c-archives",
        "title": "W3C Specref + api.w3.org + Process bikeshed source",
        "machine_readable": (
            "Specref bibliography JSON (https://api.specref.org/bibrefs?refs=...), "
            "W3C API specifications collection (https://api.w3.org/specifications), "
            "and the Process Document bikeshed source "
            "(https://raw.githubusercontent.com/w3c/w3process/main/index.bs) where "
            "RFC 2119 keywords are marked <em class=\"rfc2119\">. TR HTML is a "
            "rendered form, not the extraction SSOT."
        ),
        "discussion_history": (
            "Specref date/href, GitHub w3c/w3process history, and lists.w3.org "
            "mbox archives (group mailing lists)."
        ),
    },
    "slsa": {
        "id": "openssf-slsa",
        "title": "OpenSSF SLSA specification (HTML + GitHub repo metadata)",
        "machine_readable": (
            "Published SLSA HTML at https://slsa.dev/spec/v1.0/requirements and "
            "/provenance (in-toto Statement JSON is the attestation encoding). "
            "GitHub slsa-framework/slsa is the working-group repository; the "
            "v1.0 markdown path on GitHub 404s — HTML is the stable published form."
        ),
        "discussion_history": (
            "GitHub repo/commits/issues on slsa-framework/slsa and the on-page "
            "version banner (v1.0 producing-artifacts is marked Retired; v1.2 current)."
        ),
    },
    "mcp": {
        "id": "mcp-spec-repo",
        "title": "MCP specification repository (MDX + TypeScript/JSON Schema + commits)",
        "machine_readable": (
            "GitHub raw MDX under docs/specification/<rev>/ with BCP 14 keywords "
            "in **MUST** form; JSON Schema at schema/<rev>/schema.json generated "
            "from schema.ts (the spec names TypeScript as source of truth). "
            "GitHub commits API on the MDX path is the discussion/revision rail."
        ),
        "discussion_history": (
            "GitHub commits?path=docs/specification/... and "
            "https://github.com/modelcontextprotocol/specification/discussions"
        ),
    },
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def stored_snapshots() -> list[dict]:
    man = load_manifest()
    out = []
    for row in man.get("snapshots") or []:
        if row.get("stored") is True and row.get("path"):
            out.append(row)
    return out


def verify_lineage() -> list[dict]:
    """Rehash every stored snapshot. Second mechanical signal vs extraction."""
    rows = []
    for snap in stored_snapshots():
        rel = str(snap["path"]).replace("\\", "/")
        path = REPO / rel
        live = sha256_file(path) if path.is_file() else None
        rows.append(
            {
                "path": rel,
                "source_class": snap.get("source_class"),
                "resolved_url": snap.get("resolved_url"),
                "fetch_timestamp": snap.get("fetch_timestamp"),
                "declared_sha256": snap.get("sha256"),
                "live_sha256": live,
                "match": live == snap.get("sha256"),
                "present": path.is_file(),
                "bytes": snap.get("bytes"),
            }
        )
    return rows


def _read(rel: str) -> str:
    return (SOURCES / rel).read_text(encoding="utf-8")


def _collapse(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return text


def _sentences_with_keywords(text: str) -> list[tuple[str, str]]:
    text = _collapse(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for part in parts:
        m = KEYWORD_RE.search(part)
        if not m:
            continue
        sentence = re.sub(r"\s+", " ", part).strip()
        if len(sentence) < 24 or sentence in seen:
            continue
        seen.add(sentence)
        found.append((m.group(1), sentence[:600]))
    return found


def _section_for(text: str, sentence: str) -> str:
    idx = text.find(sentence[:40]) if sentence else -1
    window = text[: idx if idx > 0 else 0]
    m = re.findall(
        r"(?m)^(?:#{1,4}\s+)?(\d+(?:\.\d+)*)[.\s]+([A-Z][^\n]{3,80})",
        window,
    )
    if m:
        num, title = m[-1]
        return f"{num} {title.strip()[:80]}"
    hm = re.findall(r"(?m)^#{1,3}\s+(.+)$", window)
    if hm:
        return hm[-1].strip()[:80]
    return "unsectioned"


def extract_ietf() -> list[dict]:
    rfc2119 = _read("ietf/rfc2119.txt")
    rfc8174 = _read("ietf/rfc8174.txt")
    dt = json.loads(_read("ietf/rfc2119.datatracker-doc.json"))
    related = json.loads(_read("ietf/rfc2119.relateddocument.json"))
    history = dt.get("rev_history") or []
    rel_n = int((related.get("meta") or {}).get("total_count") or 0)
    out = []
    for src_id, body, doc in (
        ("rfc2119", rfc2119, "RFC 2119"),
        ("rfc8174", rfc8174, "RFC 8174"),
    ):
        for keyword, sentence in _sentences_with_keywords(body)[:8]:
            out.append(
                {
                    "id": f"ietf.{src_id}.{len(out)+1:02d}",
                    "source_class": "ietf",
                    "document": doc,
                    "keyword": keyword,
                    "section": _section_for(body, sentence),
                    "text": sentence,
                    "discussion_history": {
                        "rev_history": history,
                        "relateddocument_total_count": rel_n,
                        "relateddocument_sample": (related.get("objects") or [])[:2],
                        "notes": (
                            "RFC 8174 updates RFC 2119 (BCP 14). Datatracker "
                            "relateddocument lists contains(BCP14) and refnorm edges."
                        ),
                    },
                }
            )
    return out


def _w3c_normalize(bs: str) -> str:
    def repl(match: re.Match) -> str:
        inner = re.sub(r"<[^>]+>", "", match.group(0))
        inner = re.sub(r"\s+", " ", inner).strip()
        return inner.upper()

    return re.sub(
        r"<em[^>]*rfc2119[^>]*>[\s\S]*?</em>",
        repl,
        bs,
        flags=re.I,
    )


def extract_w3c() -> list[dict]:
    bs = _read("w3c/w3process.bs")
    specref = json.loads(_read("w3c/specref-w3c-process.json"))
    api = json.loads(_read("w3c/api-specifications.json"))
    norm = _w3c_normalize(bs)
    # Drop bikeshed boilerplate / metadata header.
    body = re.split(r"<h[12][^>]*>", norm, maxsplit=1)
    text = body[-1] if body else norm
    text = re.sub(r"<[^>]+>", " ", text)
    out = []
    for keyword, sentence in _sentences_with_keywords(text)[:10]:
        out.append(
            {
                "id": f"w3c.process.{len(out)+1:02d}",
                "source_class": "w3c",
                "document": "W3C Process Document (bikeshed source)",
                "keyword": keyword,
                "section": _section_for(text, sentence),
                "text": sentence,
                "discussion_history": {
                    "specref": specref.get("w3c-process"),
                    "github_source": "https://github.com/w3c/w3process",
                    "w3c_api_specifications_total": api.get("total"),
                    "notes": (
                        "Process keywords are marked <em class=\"rfc2119\"> in "
                        "bikeshed (often lowercase in source). Group discussion "
                        "lives on lists.w3.org mbox + GitHub issues."
                    ),
                },
            }
        )
    return out


def _html_to_text(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "\n", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&")
    html = html.replace("&quot;", '"').replace("&#39;", "'")
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html


def extract_slsa() -> list[dict]:
    html = _read("slsa/producing-artifacts.html")
    text = _html_to_text(html)
    repo = json.loads(_read("slsa/github-repo.json"))
    retired = "Retired" in text and "Version 1.2 is the current version" in text
    out = []
    for keyword, sentence in _sentences_with_keywords(text)[:10]:
        if "key words" in sentence.lower() and "RFC 2119" in sentence:
            # boilerplate BCP 14 import — keep one copy
            if any(x["id"].endswith("bcp14-import") for x in out):
                continue
            rid = "slsa.v1.0.bcp14-import"
        else:
            rid = f"slsa.v1.0.{len(out)+1:02d}"
        out.append(
            {
                "id": rid,
                "source_class": "slsa",
                "document": "SLSA v1.0 Producing artifacts (slsa.dev HTML)",
                "keyword": keyword,
                "section": _section_for(text, sentence),
                "text": sentence,
                "discussion_history": {
                    "github": {
                        "full_name": repo.get("full_name"),
                        "html_url": repo.get("html_url"),
                        "default_branch": repo.get("default_branch"),
                    },
                    "version_banner": (
                        "v1.0 page Status=Retired; site points at Version 1.2"
                        if retired
                        else "version banner not matched"
                    ),
                    "notes": (
                        "Working-group discussion is GitHub issues/PRs on "
                        "slsa-framework/slsa. Published HTML is the extraction SSOT "
                        "because the historical docs/spec/v1.0/*.md path 404s."
                    ),
                },
            }
        )
    return out


def _mdx_normalize(mdx: str) -> str:
    mdx = re.sub(r"\*\*(MUST NOT|SHALL NOT|SHOULD NOT|NOT RECOMMENDED|MUST|SHALL|REQUIRED|SHOULD|RECOMMENDED|MAY|OPTIONAL)\*\*", r"\1", mdx)
    mdx = re.sub(r"^---[\s\S]*?---\s*", "", mdx)
    mdx = re.sub(r"```[\s\S]*?```", " ", mdx)
    return mdx


def extract_mcp() -> list[dict]:
    files = [
        ("mcp/spec-index.mdx", "MCP Specification index 2025-03-26"),
        ("mcp/basic-overview.mdx", "MCP Base protocol overview 2025-03-26"),
        ("mcp/lifecycle.mdx", "MCP Lifecycle 2025-03-26"),
        ("mcp/transports.mdx", "MCP Transports 2025-03-26"),
        ("mcp/architecture.mdx", "MCP Architecture 2025-03-26"),
    ]
    commits = json.loads(_read("mcp/lifecycle.commits.json"))
    commit_rows = []
    if isinstance(commits, list):
        for c in commits[:3]:
            commit_rows.append(
                {
                    "sha": c.get("sha"),
                    "html_url": c.get("html_url"),
                    "message": ((c.get("commit") or {}).get("message") or "").split("\n")[0],
                    "date": ((c.get("commit") or {}).get("committer") or {}).get("date"),
                }
            )
    out = []
    for rel, doc in files:
        body = _mdx_normalize(_read(rel))
        for keyword, sentence in _sentences_with_keywords(body)[:6]:
            out.append(
                {
                    "id": f"mcp.{Path(rel).stem}.{len(out)+1:02d}",
                    "source_class": "mcp",
                    "document": doc,
                    "keyword": keyword,
                    "section": _section_for(body, sentence),
                    "text": sentence,
                    "discussion_history": {
                        "commits_on_lifecycle_mdx": commit_rows,
                        "discussions": "https://github.com/modelcontextprotocol/specification/discussions",
                        "schema_ssot": (
                            "TypeScript schema.ts; JSON Schema is generated "
                            "(spec index 2025-03-26)"
                        ),
                    },
                }
            )
    return out


def extract_all() -> dict[str, list[dict]]:
    return {
        "ietf": extract_ietf(),
        "w3c": extract_w3c(),
        "slsa": extract_slsa(),
        "mcp": extract_mcp(),
    }


def _surrounding_sentence(text: str, needle: str) -> str | None:
    collapsed = re.sub(r"\s+", " ", text)
    idx = collapsed.lower().find(needle.lower())
    if idx < 0:
        return None
    start = collapsed.rfind(".", 0, idx)
    start = 0 if start < 0 else start + 1
    end = collapsed.find(".", idx + len(needle))
    end = len(collapsed) if end < 0 else end + 1
    sentence = collapsed[start:end].strip()
    return sentence[:800] if sentence else None


def _keyword_in(sentence: str) -> str:
    m = KEYWORD_RE.search(sentence or "")
    return m.group(1) if m else "n/a"


def _raw_corpus() -> dict[str, tuple[str, str, dict]]:
    """source_class -> (document_label, searchable_text, discussion_history)."""
    dt = json.loads(_read("ietf/rfc2119.datatracker-doc.json"))
    related = json.loads(_read("ietf/rfc2119.relateddocument.json"))
    specref = json.loads(_read("w3c/specref-w3c-process.json"))
    api = json.loads(_read("w3c/api-specifications.json"))
    repo = json.loads(_read("slsa/github-repo.json"))
    commits = json.loads(_read("mcp/lifecycle.commits.json"))
    commit_rows = []
    if isinstance(commits, list):
        for c in commits[:3]:
            commit_rows.append(
                {
                    "sha": c.get("sha"),
                    "html_url": c.get("html_url"),
                    "message": ((c.get("commit") or {}).get("message") or "").split("\n")[0],
                }
            )
    ietf = _read("ietf/rfc2119.txt") + "\n" + _read("ietf/rfc8174.txt")
    w3c = re.sub(r"<[^>]+>", " ", _w3c_normalize(_read("w3c/w3process.bs")))
    slsa = _html_to_text(_read("slsa/producing-artifacts.html"))
    mcp = "\n".join(
        _mdx_normalize(_read(p))
        for p in (
            "mcp/spec-index.mdx",
            "mcp/basic-overview.mdx",
            "mcp/lifecycle.mdx",
            "mcp/transports.mdx",
            "mcp/architecture.mdx",
        )
    )
    return {
        "ietf": (
            "RFC 2119 + RFC 8174 (BCP 14)",
            ietf,
            {
                "rev_history": dt.get("rev_history") or [],
                "relateddocument_total_count": int(
                    (related.get("meta") or {}).get("total_count") or 0
                ),
            },
        ),
        "w3c": (
            "W3C Process Document (bikeshed source)",
            w3c,
            {
                "specref": specref.get("w3c-process"),
                "github_source": "https://github.com/w3c/w3process",
                "w3c_api_specifications_total": api.get("total"),
            },
        ),
        "slsa": (
            "SLSA v1.0 Producing artifacts (slsa.dev HTML)",
            slsa,
            {
                "github": {
                    "full_name": repo.get("full_name"),
                    "html_url": repo.get("html_url"),
                },
                "version_banner": "v1.0 Status=Retired; site points at Version 1.2",
            },
        ),
        "mcp": (
            "MCP Specification 2025-03-26 (MDX)",
            mcp,
            {
                "commits_on_lifecycle_mdx": commit_rows,
                "discussions": "https://github.com/modelcontextprotocol/specification/discussions",
            },
        ),
    }


def canonical_requirements(extracted: dict[str, list[dict]] | None = None) -> list[dict]:
    """Hand-pinned requirements used by the contradiction checker.

    Pinned against the full frozen snapshot text, not the capped sentence list,
    so a MUST that appears late in a long HTML/MDX file is still quotable.
    """
    del extracted  # callers may pass extract_all() for independence; pins use full text
    corpus = _raw_corpus()
    pins = [
        (
            "ietf.rfc2119.must-absolute",
            "ietf",
            "absolute requirement of the specification",
            "RFC 2119 §1",
        ),
        (
            "ietf.rfc8174.uppercase-only",
            "ietf",
            "only UPPERCASE usage of the key words have the defined special meanings",
            "RFC 8174 Abstract/§2",
        ),
        (
            "ietf.rfc2119.must-only-interop",
            "ietf",
            "MUST only be used where it is actually required for interoperation",
            "RFC 2119 §6",
        ),
        (
            "mcp.lifecycle.initialization-first",
            "mcp",
            "initialization phase MUST be the first interaction",
            "MCP Lifecycle / Initialization",
        ),
        (
            "mcp.basic.id-must-not-null",
            "mcp",
            "the ID MUST NOT be `null`",
            "MCP Base protocol / Requests",
        ),
        (
            "mcp.basic.receive-batches",
            "mcp",
            "MUST support receiving JSON-RPC batches",
            "MCP Base protocol / Batching",
        ),
        (
            "mcp.transports.stdio-no-embedded-newlines",
            "mcp",
            "MUST NOT contain embedded newlines",
            "MCP Transports / stdio",
        ),
        (
            "mcp.transports.utf8",
            "mcp",
            "JSON-RPC messages MUST be UTF-8 encoded",
            "MCP Transports",
        ),
        (
            "slsa.v1.0.provenance-exists",
            "slsa",
            "build process MUST generate provenance that unambiguously identifies",
            "SLSA v1.0 Provenance generation / Exists",
        ),
        (
            "slsa.v1.0.provenance-authentic",
            "slsa",
            "Consumers MUST be able to validate the authenticity of the provenance",
            "SLSA v1.0 Provenance is Authentic",
        ),
        (
            "w3c.process.minutes-public",
            "w3c",
            "Official meeting minutes and other records of decisions made MUST",
            "W3C Process (bikeshed)",
        ),
    ]
    out = []
    for rid, cls, needle, section_hint in pins:
        label, text, hist = corpus[cls]
        sentence = _surrounding_sentence(text, needle)
        if not sentence:
            continue
        out.append(
            {
                "id": rid,
                "source_class": cls,
                "document": label,
                "keyword": _keyword_in(sentence),
                "section": section_hint,
                "section_hint": section_hint,
                "text": sentence,
                "discussion_history": hist,
                "pinned": True,
            }
        )
    return out
