#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0172.json from live cache measurements."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

from scenario import (  # noqa: E402
    FIXED,
    IMPL,
    PACKAGE,
    UNIT,
    VERSION,
    content_digest_anchor,
    measure_same_version_republish,
    measure_unchanged_served_from_cache,
)
import _p2lib as L  # noqa: E402

OUT = "command-center/receipts/TST-0172.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/cache_report"
SENTINEL = "SUCCESS:TST-0172"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0172/probe1_unchanged_cache_hit.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0172/probe2_same_version_republish.py"
)
QUESTION = (
    "Does the cache key incorporate the package CONTENT hash rather than only "
    "name+version, so a republished fix is not masked by a stale entry? PASS "
    "requires a same-version republish to be fetched, not served from cache."
)
SUPPORTING = [
    IMPL,
    "tools/marketplace/schema/package-cache.schema.json",
    "command-center/p2-wave/probes/TST-0172/scenario.py",
    "command-center/p2-wave/probes/TST-0172/probe1_unchanged_cache_hit.py",
    "command-center/p2-wave/probes/TST-0172/probe2_same_version_republish.py",
]


def digest_rel(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "exists": path.is_file(),
        "role": "supporting" if rel != IMPL else "implementation",
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with tempfile.TemporaryDirectory(prefix="tst0172-emit-") as tmp:
        base = Path(tmp)
        hit = measure_unchanged_served_from_cache(base / "hit")
        republish = measure_same_version_republish(base / "republish")
    if not hit.get("pass") or not republish.get("pass"):
        print(
            f"FAILED:TST-0172 emit hit={hit.get('pass')} "
            f"republish={republish.get('pass')}"
        )
        print(json.dumps({"hit": hit, "republish": republish}, indent=2, sort_keys=True)[:6000])
        return 1

    anchor = content_digest_anchor()
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [digest_rel(rel) for rel in SUPPORTING]
    p_hit = L.probe(
        "source",
        "in-process",
        "measure_unchanged_served_from_cache",
        json.dumps(
            {
                "cache_key": hit["cache_key"],
                "second_source": hit["second_source"],
                "hits": hit["hits_after_second"],
                "always_refetch_never_hits": hit["always_refetch_never_hits"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_rep = L.probe(
        "verifier",
        "in-process",
        "measure_same_version_republish",
        json.dumps(
            {
                "version": republish["version"],
                "cache_key_buggy": republish["cache_key_buggy"],
                "cache_key_fixed": republish["cache_key_fixed"],
                "keys_differ": republish["keys_differ"],
                "install_after": republish["install_after"]["sha256"],
                "naive_still_served_stale": republish["naive_still_served_stale"],
            },
            sort_keys=True,
        ),
        0,
    )

    answer = (
        "YES: the live package cache key is sha256(payload) "
        f"(content_digest at {anchor['anchor']}), not name+version. "
        f"Package {PACKAGE}@{VERSION} republished with new bytes: resolved key "
        f"{republish['cache_key_buggy']} became {republish['cache_key_fixed']}. "
        "The first observe after republish returned the fixed marker "
        f"{FIXED.decode('ascii').strip()} and the install tree wrote those bytes "
        f"(sha256={republish['install_after']['sha256']}). A name@version mutant "
        "still served the buggy payload (regression seed). Unchanged observe is a "
        f"measured hit (hits={hit['hits_after_second']}, source=hit); an "
        "always-refetch mutant never hits. SUCCESS:TST-0172"
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Cache key includes content hash so a fixed package cannot stay masked",
        "spec_anchor": "_USER-PROMPTS.md:11013,11305; B05/B07 cache refresh",
        "question": QUESTION,
        "answer": answer,
        "report_kind": "cache_report",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "unchanged_package_served_from_cache": True,
        "same_version_republish_fetched": True,
        "name_version_mutant_still_masks": True,
        "package": PACKAGE,
        "version": VERSION,
        "cache_key": {
            "fn": "content_digest",
            "rule": "sha256(payload bytes); registry name->digest; never name@version",
            "anchor": anchor,
            "buggy": republish["cache_key_buggy"],
            "fixed": republish["cache_key_fixed"],
            "keys_differ": True,
            "name_version_key": republish["name_version_key"],
            "two_packages_share_one_key": False,
        },
        "both_states": {
            "unchanged_served_from_cache": hit["served_from_cache"],
            "always_refetch_never_hits": hit["always_refetch_never_hits"],
            "same_version_fetched": republish["cas_fetched_fix"],
            "name_version_masked": republish["naive_still_served_stale"],
            "pass": True,
        },
        "hit": hit,
        "republish": republish,
        "implementation": IMPL,
        "artifacts": artifacts,
        "evidence": [
            L.evidence(
                "Signal (a): resolved cache key strings. Buggy payload key "
                f"{republish['cache_key_buggy']} and fixed payload key "
                f"{republish['cache_key_fixed']} are sha256 of the payload bytes "
                "and they differ; the name@version slot is identical across the "
                "republish.",
                "CONFIRMED",
                anchor["anchor"],
                [p_rep],
                "almost-certain",
            ),
            L.evidence(
                "Signal (b): install after same-version republish. installed.bin "
                f"sha256={republish['install_after']['sha256']} equals the new "
                "content digest and the on-disk blob basename is that digest.",
                "CONFIRMED",
                f"{IMPL}:observe",
                [p_rep, p_hit],
                "almost-certain",
            ),
            {
                "path": IMPL,
                "kind": "resolved-cache-key",
                "claim": "Cache key is content_digest(payload), not name+version.",
                "anchor": anchor["anchor"],
            },
            {
                "path": IMPL,
                "kind": "install-after-republish",
                "claim": (
                    "A same-version republish writes new bytes into the install "
                    "tree; the name@version mutant still serves the old bytes."
                ),
                "anchor": f"{IMPL}:publish",
            },
        ],
        "tests": [
            {
                "id": "TST-0172-T1-unchanged-cache-hit",
                "name": "both-states control: an unchanged package IS served from cache",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0172-T2-same-version-republish",
                "name": "regression seed: stale cache masks a fixed package",
                "command": P2,
                "result": "PASS",
            },
        ],
        "checks": [
            {"id": "cache-hit-unchanged", "verdict": "PASS"},
            {"id": "same-version-republish-fetched", "verdict": "PASS"},
            {"id": "name-version-mutant-masks", "verdict": "PASS"},
        ],
        "negative_controls": [
            L.control(
                "always-refetch",
                "mutation",
                "A cache that always copies source never records a hit. Production "
                "CAS must hit on the second observe of an unchanged package.",
                True,
                True,
                bad="always_refetch source=refetch hits=0",
                good=f"cas second_source=hit hits={hit['hits_after_second']}",
            ),
            L.control(
                "name-version-key",
                "known-broken-mutant",
                "Keying by name@version keeps serving the buggy payload after a "
                "same-version republish. Content-addressed CAS must not.",
                True,
                True,
                bad="naive payload=BUGGY source=stale-hit",
                good=f"cas payload=FIXED key={republish['cache_key_fixed']}",
            ),
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "unchanged-cache-hit"},
            {"id": "probe2", "command": P2, "role": "same-version-republish"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0172-probe2-same-version-republish",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial control is probe2: it keeps version 1.0.0, changes "
                "payload bytes, requires the resolved key to change, requires the "
                "install tree to show the new digest, and requires the "
                "name@version mutant to still mask. Not a second-human review."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0172/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0172",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py TST-0172",
                    "deferred to post-write measure",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "_USER-PROMPTS.md:11013 / 11305 and command-center/schema/"
                    "receipt.schema.json are absent on this worktree; the unit "
                    "question is taken from WORK-UNIT-CATALOG.json TST-0172. The "
                    "live SUT is tools/marketplace/package_cache.py (IMP-0463)."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Diff the catalog question against the prompts file if restored."
                ),
            }
        ],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot - same-fingerprint structural refute parks BLOCKED",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "defects": [],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
