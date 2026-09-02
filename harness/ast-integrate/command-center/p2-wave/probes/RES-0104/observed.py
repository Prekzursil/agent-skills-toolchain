#!/usr/bin/env python3
"""Recompute catalog sizes from stored capture bytes. No network."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"


def marketplace_total(raw: bytes) -> int:
    doc = json.loads(raw.decode("utf-8"))
    results = doc["results"]
    if not isinstance(results, list) or not results:
        raise ValueError("marketplace results empty")
    for meta in results[0].get("resultMetadata") or []:
        if meta.get("metadataType") == "ResultCount":
            for item in meta.get("metadataItems") or []:
                if item.get("name") == "TotalCount":
                    return int(item["count"])
    raise ValueError("marketplace TotalCount missing")


def npm_total(raw: bytes) -> int:
    doc = json.loads(raw.decode("utf-8"))
    return int(doc["total"])


def k8s_openapi_v3_count(raw: bytes) -> int:
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, list):
        raise ValueError("k8s listing not a list")
    return len(doc)


def load() -> dict:
    return {
        "vscode_marketplace_extensions": marketplace_total(
            (CAP / "vscode-marketplace-query.bin").read_bytes()
        ),
        "npm_search_total": npm_total((CAP / "npm-search-total.bin").read_bytes()),
        "npm_search_query": "boost-exact:false",
        "npm_page_size_max": 250,
        "k8s_openapi_v3_documents": k8s_openapi_v3_count(
            (CAP / "k8s-openapi-v3-listing.bin").read_bytes()
        ),
        "k8s_unaggregated_break_requests": 80,
        "k8s_tag": "v1.32.2",
    }


if __name__ == "__main__":
    print(json.dumps(load(), indent=2, sort_keys=True))
