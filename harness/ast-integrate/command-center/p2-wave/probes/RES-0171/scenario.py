"""Executable scenarios for RES-0171: both-states, key sensitivity, corrupt.

Origins are local fixtures. Fetch counts prove reuse vs refetch.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

from cache_key import (
    KEY_FIELDS,
    REQUIRED_QUESTION_FIELDS,
    InvalidResearchCacheKey,
    derive_cache_key,
)
from policy import (
    SOURCE_CLASSES,
    UNMEASURED_BUCKET,
    policy_table,
    time_bucket,
)
from resume import request_inputs, resume_one
from store import ResearchResultCache

HERE = Path(__file__).resolve().parent
ORIGIN = HERE / "fixtures" / "origin"
REPO = HERE.parents[3]

STABLE_PAGE = "stable-page.json"
MUTATED_PAGE = "mutated-page.json"

BASE = {
    "query": "research cache key resume semantics",
    "backend": "fixture-search",
    "filters": {"lang": "en", "site": None, "date_range": "none"},
    "backend_version": "fixture-search/1.0.0",
    "source_class": "official-docs",
    "kind": "fetch",
}


def _load_page(name: str) -> bytes:
    return (ORIGIN / name).read_bytes()


def run_both_states(now_unix: int = 1_700_000_000) -> dict[str, Any]:
    """Resume reuses an unchanged origin and refetches a mutated origin."""
    fetches = {"stable": 0, "mutated": 0}
    stable = {"bytes": _load_page(STABLE_PAGE)}
    mutated = {"bytes": _load_page(MUTATED_PAGE)}
    first_mutated = bytes(mutated["bytes"])

    def fetch_stable() -> bytes:
        fetches["stable"] += 1
        return stable["bytes"]

    def fetch_mutated() -> bytes:
        fetches["mutated"] += 1
        return mutated["bytes"]

    with tempfile.TemporaryDirectory(prefix="res0171-both-") as tmp:
        cache = ResearchResultCache(Path(tmp) / "cache")
        req_s = request_inputs(now_unix=now_unix, **{**BASE, "query": "stable-doc"})
        req_m = request_inputs(now_unix=now_unix, **{**BASE, "query": "mutated-doc"})

        first_s = resume_one(
            cache,
            req_s,
            fetch_stable,
            now_unix=now_unix,
            origin_id="stable",
            revalidate=lambda _stored: stable["bytes"],
        )
        first_m = resume_one(
            cache,
            req_m,
            fetch_mutated,
            now_unix=now_unix,
            origin_id="mutated",
            revalidate=lambda _stored: mutated["bytes"],
        )
        if first_s["action"] != "miss" or first_m["action"] != "miss":
            return {
                "pass": False,
                "why": "first-run-not-miss",
                "first_s": first_s["action"],
                "first_m": first_m["action"],
            }

        resume_s = resume_one(
            cache,
            req_s,
            fetch_stable,
            now_unix=now_unix + 30,
            origin_id="stable",
            revalidate=lambda _stored: fetch_stable(),
        )

        mutated["bytes"] = (
            b'{"page":"mutated-page","rev":2,"body":"CHANGED-AFTER-CACHE"}\n'
        )
        resume_m = resume_one(
            cache,
            req_m,
            fetch_mutated,
            now_unix=now_unix + 30,
            origin_id="mutated",
            revalidate=lambda _stored: fetch_mutated(),
        )

        reuse_ok = resume_s["action"] == "reuse" and resume_s["body"] == stable["bytes"]
        refetch_ok = (
            resume_m["action"] == "refetch"
            and resume_m["body"] == mutated["bytes"]
            and resume_m["body"] != first_mutated
        )
        return {
            "pass": bool(reuse_ok and refetch_ok and first_s["key"] != first_m["key"]),
            "stable_first_action": first_s["action"],
            "mutated_first_action": first_m["action"],
            "stable_resume_action": resume_s["action"],
            "mutated_resume_action": resume_m["action"],
            "stable_body_unchanged": resume_s["body"] == stable["bytes"],
            "mutated_body_changed": resume_m["body"] != first_mutated,
            "fetches": dict(fetches),
            "counters": cache.counters.as_dict(),
            "stable_key": first_s["key"],
            "mutated_key": first_m["key"],
            "keys_distinct": first_s["key"] != first_m["key"],
            "time_bucket": first_s["time_bucket"],
        }


def run_key_sensitivity(now_unix: int = 1_700_000_000) -> dict[str, Any]:
    """Changing any required field must change the key (one at a time)."""
    base = request_inputs(now_unix=now_unix, **BASE)
    base_key = derive_cache_key(base)
    variants = {
        "query": "research cache key resume semantics CHANGED",
        "backend": "fixture-search-B",
        "filters": {"lang": "de", "site": None, "date_range": "none"},
        "time_bucket": "ttl-3600s:b0",
        "backend_version": "fixture-search/9.9.9",
        "source_class": "papers",
        "kind": "search",
    }
    mutations: list[dict[str, Any]] = []
    distinct = {base_key}
    for field, new_val in variants.items():
        mutated = dict(base)
        mutated[field] = new_val
        new_key = derive_cache_key(mutated)
        changed = new_key != base_key
        distinct.add(new_key)
        mutations.append({"field": field, "changed": changed, "new_key": new_key})

    omitted_collides = False
    try:
        derive_cache_key({k: v for k, v in base.items() if k != "backend_version"})
        omitted_rejected = False
        omitted_collides = True
    except InvalidResearchCacheKey as exc:
        omitted_rejected = exc.field == "backend_version"

    all_changed = all(m["changed"] for m in mutations)
    question_fields_ok = all(
        any(m["field"] == f and m["changed"] for m in mutations)
        for f in REQUIRED_QUESTION_FIELDS
    )
    return {
        "pass": all_changed
        and question_fields_ok
        and omitted_rejected
        and not omitted_collides,
        "base_key": base_key,
        "mutations": mutations,
        "distinct_keys": len(distinct),
        "required_question_fields": list(REQUIRED_QUESTION_FIELDS),
        "all_key_fields": list(KEY_FIELDS),
        "omitted_backend_version_rejected": omitted_rejected,
    }


def run_corrupt_never_served(now_unix: int = 1_700_000_000) -> dict[str, Any]:
    fetches = {"n": 0}
    origin = _load_page(STABLE_PAGE)

    def fetcher() -> bytes:
        fetches["n"] += 1
        return origin

    with tempfile.TemporaryDirectory(prefix="res0171-corrupt-") as tmp:
        cache = ResearchResultCache(Path(tmp) / "cache")
        req = request_inputs(now_unix=now_unix, **BASE)
        first = resume_one(
            cache, req, fetcher, now_unix=now_unix, origin_id="stable"
        )
        key = first["key"]
        body_path = cache.payload_path(key)
        flipped = bytearray(body_path.read_bytes())
        flipped[0] ^= 0x01
        body_path.write_bytes(bytes(flipped))
        flipped_sha_on_disk = hashlib.sha256(bytes(flipped)).hexdigest()
        second = resume_one(
            cache,
            req,
            fetcher,
            now_unix=now_unix + 1,
            origin_id="stable",
            revalidate=lambda _s: origin,
        )
        served_flipped = second["body"] == bytes(flipped)
        return {
            "pass": (
                not served_flipped
                and second["action"] == "corrupt-refetch"
                and second["body"] == origin
                and fetches["n"] == 2
            ),
            "first_action": first["action"],
            "second_action": second["action"],
            "served_flipped": served_flipped,
            "fetcher_calls": fetches["n"],
            "flipped_sha_on_disk": flipped_sha_on_disk,
        }


def run_unmeasured_bucket_clock_free() -> dict[str, Any]:
    a = time_bucket("official-docs", 10)
    b = time_bucket("official-docs", 10_000_000)
    measured = {"official-docs": 3600}
    c = time_bucket("official-docs", 3600, measured)
    d = time_bucket("official-docs", 7199, measured)
    e = time_bucket("official-docs", 7200, measured)
    return {
        "pass": a == b == UNMEASURED_BUCKET and c == d and e != c,
        "unmeasured_a": a,
        "unmeasured_b": b,
        "measured_same_bucket": c == d,
        "measured_next_bucket": e,
        "constant": UNMEASURED_BUCKET,
    }


def run_all(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    both = run_both_states()
    keys = run_key_sensitivity()
    corrupt = run_corrupt_never_served()
    clock = run_unmeasured_bucket_clock_free()
    table = policy_table(root)
    return {
        "both_states": both,
        "key_sensitivity": keys,
        "corrupt": corrupt,
        "clock": clock,
        "policy": table,
        "source_class_count": len(SOURCE_CLASSES),
        "pass": (
            bool(both.get("pass"))
            and bool(keys.get("pass"))
            and bool(corrupt.get("pass"))
            and bool(clock.get("pass"))
            and table["unmeasured_class_count"] == len(SOURCE_CLASSES)
            and not table["res0006_present"]
        ),
    }


def snippet_at(path: Path, needle: str) -> tuple[int, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return i, line.strip()
    return 0, ""
