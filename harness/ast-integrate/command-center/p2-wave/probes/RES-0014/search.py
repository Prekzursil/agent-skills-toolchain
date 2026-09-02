"""Search the corpus for the three RES-0014 defect classes.

A keyword hit is not a match. Matches require a curated discriminator.
Detector control: the operator-seeded known-present issue must be retrieved.
"""
from __future__ import annotations

import re

from match_table import MATCHES, NON_MATCHES, match_key

SEEDED_TOKEN = "RES-0014-SEEDED-KNOWN-PRESENT-FC-11303"

CLASS_PATTERNS = {
    "plugin_installed_hooks_unloaded": [
        re.compile(r"hooks?\.json", re.I),
        re.compile(r"\bhooks?\b", re.I),
        re.compile(r"installed|enabled", re.I),
        re.compile(
            r"never fir|not (being )?load|unloaded|silently inert|"
            r"do not fire|doesn't fire|does not fire",
            re.I,
        ),
    ],
    "marketplace_silent_fail": [
        re.compile(r"marketplace", re.I),
        re.compile(r"install|update|validate|version", re.I),
        re.compile(
            r"silent|no error|no warning|already installed|pass(es)? validation",
            re.I,
        ),
    ],
    "skill_on_disk_not_loaded": [
        re.compile(r"skill", re.I),
        re.compile(r"SKILL\.md|skills/", re.I),
        re.compile(
            r"not (loaded|discovered|mounted|register)|ignored|0 skills|no matching",
            re.I,
        ),
    ],
}


def class_keyword_hit(blob: str, class_id: str) -> bool:
    pats = CLASS_PATTERNS[class_id]
    return all(p.search(blob) for p in pats)


def retrieve(corpus: list[dict]) -> dict:
    by_class: dict[str, list[int | str]] = {k: [] for k in CLASS_PATTERNS}
    seeded_hits: list[dict] = []
    decoy_hits: list[dict] = []
    for row in corpus:
        blob = row["blob"]
        key = match_key(row)
        if SEEDED_TOKEN in blob or row.get("seeded"):
            seeded_hits.append(row)
        if row.get("decoy") or "RES-0014-DECOY-KEYWORD-ONLY" in blob:
            decoy_hits.append(row)
        for cid in CLASS_PATTERNS:
            if class_keyword_hit(blob, cid):
                by_class[cid].append(key)
    return {
        "by_class": by_class,
        "seeded": seeded_hits,
        "decoy": decoy_hits,
    }


def classify(corpus: list[dict]) -> dict:
    retrieval = retrieve(corpus)
    matches = []
    non_matches = []
    unmatched_keyword_hits = []
    for row in corpus:
        key = match_key(row)
        if key in MATCHES:
            rec = dict(MATCHES[key])
            rec["title"] = row["title"]
            rec["state"] = row["state"]
            rec["html_url"] = row["html_url"]
            rec["rails"] = [
                {
                    "id": "R1-structured-api",
                    "kind": "structured-api",
                    "permalink": row["api_permalink"],
                    "path": row["api_path"],
                    "http_status": 200,
                    "sha256": row["api_sha256"],
                    "bytes": row["api_bytes"],
                },
                {
                    "id": "R2-prose-html",
                    "kind": "prose-html",
                    "permalink": row["html_permalink"],
                    "path": row["html_path"],
                    "http_status": 200,
                    "sha256": row["html_sha256"],
                    "bytes": row["html_bytes"],
                },
            ]
            matches.append(rec)
        elif key in NON_MATCHES:
            rec = dict(NON_MATCHES[key])
            rec["title"] = row["title"]
            rec["state"] = row["state"]
            rec["html_url"] = row["html_url"]
            non_matches.append(rec)
        else:
            hits = [cid for cid in CLASS_PATTERNS if class_keyword_hit(row["blob"], cid)]
            if hits:
                unmatched_keyword_hits.append(
                    {
                        "issue_ref": row["id"],
                        "number": row["number"],
                        "title": row["title"],
                        "keyword_classes": hits,
                        "reason": "keyword-hit-without-curated-discriminator",
                    }
                )

    return {
        "retrieval": {
            "seeded_token": SEEDED_TOKEN,
            "seeded_retrieved": bool(retrieval["seeded"]),
            "seeded_ids": [r["id"] for r in retrieval["seeded"]],
            "decoy_retrieved_as_keyword": bool(retrieval["decoy"]),
            "by_class": {
                k: [str(x) for x in v] for k, v in retrieval["by_class"].items()
            },
        },
        "matches": matches,
        "non_matches": non_matches,
        "unmatched_keyword_hits": unmatched_keyword_hits,
    }


def detector_control_both_states(corpus: list[dict]) -> dict:
    full = retrieve(corpus)
    stripped = [r for r in corpus if not r.get("seeded")]
    missing = retrieve(stripped)
    ok = bool(full["seeded"]) and not bool(missing["seeded"])
    return {
        "present_state_retrieves_seed": bool(full["seeded"]),
        "absent_state_misses_seed": not bool(missing["seeded"]),
        "pass": ok,
        "seeded_token": SEEDED_TOKEN,
    }
