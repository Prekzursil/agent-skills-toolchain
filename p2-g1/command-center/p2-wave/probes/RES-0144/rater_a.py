"""Rater A: publisher-class. URL host/path + exact-body sha256 cluster.

Does not read n-gram overlap, first-person voice, or gold labels.
Vendor-role analog: openai-mechanical-publisher-class.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse

from rubric import AUTHORITY_LEVELS, INDEPENDENCE_LEVELS, LOW_INDEPENDENCE

PRIMARY_HOSTS = frozenset(
    {
        "www.rfc-editor.org",
        "rfc-editor.org",
        "www.ietf.org",
        "datatracker.ietf.org",
        "peps.python.org",
        "spdx.org",
        "www.iana.org",
        "iana.org",
        "json-schema.org",
    }
)
MAINTAINER_HOSTS = frozenset(
    {
        "docs.python.org",
        "packaging.python.org",
        "www.python.org",
        "python.org",
        "pypi.org",
        "docs.pypi.org",
        "numpy.org",
        "warehouse.pypa.io",
    }
)
PRACTITIONER_HOSTS = frozenset(
    {
        "lab.example",
        "ops.example",
        "incident.example",
        "postmortem.example",
    }
)
RETELLER_HOSTS = frozenset(
    {
        "wire.example",
        "news.example",
        "mirror.example",
        "digest.example",
        "roundup.example",
        "tutorial.example",
        "so.example",
        "newsletter.example",
        "blog.example",
    }
)
CITE_RE = re.compile(
    r"\b(according to|as reported by|sources say|as explained in)\b",
    re.I,
)
TOPIC_KEYS = (
    "rfc2119",
    "rfc8259",
    "pep-0008",
    "pep-0508",
    "pep8",
    "hashlib",
    "gil",
    "json-schema",
    "jsonschema",
    "spdx",
    "mit",
    "iana",
    "pip",
    "requests",
    "cpython",
    "numpy",
    "packaging",
    "media-types",
)


def body_sha256(body: str) -> str:
    raw = body.replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def topic_from_url(url: str) -> str:
    u = url.lower()
    for key in TOPIC_KEYS:
        if key in u:
            return key
    path = urlparse(url).path.lower()
    for key in TOPIC_KEYS:
        if key in path:
            return key
    return "other"


def publisher_class(url: str) -> str:
    p = urlparse(url)
    host = (p.netloc or "").lower()
    path = (p.path or "").lower()
    if host in PRIMARY_HOSTS:
        return "primary"
    if host in MAINTAINER_HOSTS:
        return "maintainer"
    if host in PRACTITIONER_HOSTS:
        return "practitioner"
    if host in RETELLER_HOSTS:
        return "reteller"
    if host in {"github.com", "raw.githubusercontent.com"}:
        if "hashlib.py" in path:
            return "primary"
        if path.endswith("/license") or "/license." in path or path.endswith("/license.txt"):
            return "primary"
        if "/issues/" in path:
            return "practitioner"
        if "contributing" in path or "readme" in path:
            return "maintainer"
        return "maintainer"
    return "reteller"


def authority_from_class(cls: str) -> str:
    return {
        "primary": "PRIMARY",
        "maintainer": "MAINTAINER",
        "practitioner": "PRACTITIONER",
        "reteller": "RETELLER",
    }[cls]


def score_one(src: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    url = str(src.get("url") or "")
    body = str(src.get("body") or "")
    leaked = [k for k in src.keys() if k in {"gold_authority", "gold_independence", "expected", "label"}]
    cls = publisher_class(url)
    authority = authority_from_class(cls)
    digest = body_sha256(body)
    cluster = [s["id"] for s in corpus if body_sha256(str(s.get("body") or "")) == digest]
    topic = topic_from_url(url)
    if len(cluster) >= 2:
        independence = "SYNDICATED"
        why = f"exact-sha256 cluster size={len(cluster)}"
    elif cls == "reteller":
        independence = "DERIVED"
        why = "reteller-host without exact twin; restatement not observation"
    elif cls == "practitioner":
        peers = []
        for other in corpus:
            if other.get("id") == src.get("id"):
                continue
            ou = str(other.get("url") or "")
            if publisher_class(ou) != "practitioner":
                continue
            if topic_from_url(ou) != topic or topic == "other":
                continue
            if body_sha256(str(other.get("body") or "")) == digest:
                continue
            peers.append(other["id"])
        if peers:
            independence = "PARALLEL"
            why = f"practitioner topic={topic} peers={peers}"
        else:
            independence = "ORIGINATING"
            why = f"practitioner unique-hash topic={topic}"
    else:
        independence = "ORIGINATING"
        why = f"publisher-class={cls} unique-hash"
    if CITE_RE.search(body) and independence == "ORIGINATING" and cls == "reteller":
        independence = "DERIVED"
        why = "citation-marker on reteller host"
    return {
        "id": src.get("id"),
        "rater": "A",
        "vendor_role": "openai-mechanical-publisher-class",
        "publisher_class": cls,
        "topic": topic,
        "body_sha256": digest,
        "cluster_ids": sorted(cluster),
        "authority": authority,
        "independence": independence,
        "low_independence": independence in LOW_INDEPENDENCE,
        "why": why,
        "forbidden_keys_seen": leaked,
        "features_used": ["url", "body_sha256"],
        "axis_vocab": {"authority": list(AUTHORITY_LEVELS), "independence": list(INDEPENDENCE_LEVELS)},
    }


def score_all(corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [score_one(src, corpus) for src in corpus]
