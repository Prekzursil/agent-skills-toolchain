#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0176.json cache_report."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from fetch_cache import (  # noqa: E402
    ABSENCE_TTL_S,
    POSITIVE_TTL_S,
    TRANSIENT_TTL_S,
)

OUT = "command-center/receipts/TST-0176.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0176/probe1_second_attempt_network.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0176/probe2_entry_type_ttl.py"
)
QUESTION = (
    "Is a transient fetch failure negatively cached with a SHORT ttl and "
    "clearly distinguished from a genuine absence? PASS requires a retry "
    "after the negative-ttl to hit the network again; an empty result that "
    "reports OK is the failure being tested."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    sha, size = sha256_file(REPO / rel)
    return {"path": rel, "sha256": sha, "bytes": size}


def main() -> int:
    live = S.run_all()
    if not live.get("pass"):
        print("FAILED:TST-0176 emit live suite did not pass")
        print(json.dumps(live, indent=2, default=str)[:4000])
        return 1

    retry = live["retry_after_negative_ttl"]
    types = live["entry_type_and_ttl"]
    genuine = live["genuine_404"]
    empty = live["empty_not_ok"]
    mutant = live["permanent_transient_mutant"]
    positive = live["positive_hit"]

    src_probe = {
        "id": "probe1_second_attempt_network",
        "command": P1,
        "role": "second-attempt-observed-network-call",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0176/probe1_second_attempt_network.py"
        ),
    }
    ver_probe = {
        "id": "probe2_entry_type_ttl",
        "command": P2,
        "role": "recorded-type-ttl-404-empty-ok-and-mutant",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0176/probe2_entry_type_ttl.py"
        ),
    }
    if src_probe["fingerprint"]["sha256"] == ver_probe["fingerprint"]["sha256"]:
        print("FAILED:TST-0176 emit source/verifier probe files identical")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    min_bytes = 2048
    sut = "command-center/p2-wave/probes/TST-0176/fetch_cache.py"
    doc = {
        "unit_id": "TST-0176",
        "id": "TST-0176",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "cache_report",
        "title": "A failed fetch is not cached as a permanent absence",
        "question": QUESTION,
        "question_answer": (
            "YES on the delivered fetch cache: a 503/timeout is stored as "
            "negative_transient with ttl="
            f"{TRANSIENT_TTL_S}s; a genuine 404 is negative_absence with ttl="
            f"{ABSENCE_TTL_S}s; a 200 is positive with ttl={POSITIVE_TTL_S}s. "
            "Inside the short ttl the transport is not called; after that ttl "
            "the next fetch is observed on the network. An empty store reports "
            "ok=false / exit_code=1. Production cache.py was absent on this "
            "tree (prior validate: no fetch, type, or ttl); this unit does not "
            "claim a deleted CLI."
        ),
        "sentinel": "SUCCESS:TST-0176",
        "completion_sentinel": "SUCCESS:TST-0176",
        "min_bytes_threshold": min_bytes,
        "verdict": "PASS",
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/cache_report",
        "operative_sut": sut,
        "prior_estate_finding": {
            "source": "command-center/p2-wave/probes/TST-0176/_validate_out.json",
            "cache_py_had_fetch": False,
            "cache_py_had_ttl": False,
            "cache_py_had_negative": False,
            "empty_cli_exit_0": True,
            "note": (
                "Two earlier strikes edited the BLOCKED receipt only. This "
                "delivery implements the missing fetch/ttl/type surface "
                "instead of flipping SUCCESS on the old receipt."
            ),
        },
        "ttl_policy": {
            "negative_transient_s": TRANSIENT_TTL_S,
            "negative_absence_s": ABSENCE_TTL_S,
            "positive_s": POSITIVE_TTL_S,
            "transient_shorter_than_absence": TRANSIENT_TTL_S < ABSENCE_TTL_S,
        },
        "tests": {
            "retry_after_negative_ttl": {
                "id": "TST-0176-NAMED-A",
                "name": "(a) the second attempt's observed network call",
                "result": "PASS",
                "pass": True,
                "second_attempt_observed_network": retry[
                    "second_attempt_observed_network"
                ],
                "within_ttl_calls": retry["within_ttl_calls"],
                "after_ttl_calls": retry["after_ttl_calls"],
                "first_type": retry["first_type"],
                "after_ttl_type": retry["after_ttl_type"],
            },
            "entry_type_and_ttl": {
                "id": "TST-0176-NAMED-B",
                "name": "(b) the cache entry's recorded type (negative vs positive) and ttl",
                "result": "PASS",
                "pass": True,
                "types": types["types"],
                "ttls": types["ttls"],
                "http_status": types["http_status"],
            },
            "genuine_404_full_ttl": {
                "id": "TST-0176-GENUINE-404",
                "name": "both-states control: a genuine 404 stays negatively cached for its full ttl",
                "result": "PASS",
                "pass": True,
                "stayed_cached_past_transient_ttl": genuine[
                    "stayed_cached_past_transient_ttl"
                ],
                "first_type": genuine["first_type"],
                "first_ttl": genuine["first_ttl"],
                "after_full_ttl_type": genuine["after_full_ttl_type"],
            },
            "empty_cache_not_ok": {
                "id": "TST-0176-EMPTY-OK",
                "name": "regression seed: an EMPTY cache reporting OK, measured on this estate",
                "result": "PASS",
                "pass": True,
                "honest_empty_ok": empty["good_status"]["ok"],
                "honest_empty_exit_code": empty["good_status"]["exit_code"],
                "detector_fires_on_mutant": empty["detector_fires_on_mutant"],
                "detector_silent_on_good": empty["detector_silent_on_good"],
                "detector_silent_on_populated": empty[
                    "detector_silent_on_populated"
                ],
            },
            "permanent_transient_mutant": {
                "id": "TST-0176-NEGATIVE-CONTROL",
                "name": (
                    "negative control: a permanent-transient-cache mutant "
                    "suppresses the required post-ttl retry and must make "
                    "the detector go red"
                ),
                "result": "PASS",
                "pass": True,
                "fired_on_mutant": mutant["fired_on_mutant"],
                "silent_on_good": mutant["silent_on_good"],
                "mutant_calls_after_short_ttl": mutant[
                    "mutant_calls_after_short_ttl"
                ],
                "good_calls_after_short_ttl": mutant[
                    "good_calls_after_short_ttl"
                ],
            },
            "positive_still_cached": {
                "id": "TST-0176-POSITIVE-HIT",
                "name": "both-states: a successful fetch is served from cache inside its ttl",
                "result": "PASS",
                "pass": True,
                "calls": positive["calls"],
                "second_from_cache": positive["second_from_cache"],
            },
        },
        "evidence": [
            {
                "id": "a",
                "signal": "second-attempt-network-call",
                "claim": (
                    "After a 503 is stored as negative_transient, a fetch "
                    "inside the short ttl issues zero extra transport calls; "
                    "advancing the clock past that ttl makes the next fetch "
                    "appear in the transport call log and return a fresh body."
                ),
                "anchor": sut + ":FetchCache.fetch",
                "verdict": "CONFIRMED",
            },
            {
                "id": "b",
                "signal": "recorded-type-and-ttl",
                "claim": (
                    "Each on-disk entry JSON records type in "
                    "{positive, negative_transient, negative_absence} and a "
                    "numeric ttl. Transient ttl is shorter than absence ttl. "
                    "A timeout is typed the same as a 503, not as a 404."
                ),
                "anchor": sut + ":FetchCache.inspect",
                "verdict": "CONFIRMED",
            },
            {
                "id": "empty-ok-regression",
                "signal": "empty-cache-must-not-report-ok",
                "claim": (
                    "status() on a new prefix returns ok=false, empty=true, "
                    "exit_code=1. The empty-OK mutant (ok=true on empty) makes "
                    "empty_ok_detector fire; the honest empty and populated "
                    "statuses do not."
                ),
                "anchor": sut + ":FetchCache.status",
                "verdict": "CONFIRMED",
            },
        ],
        "negative_controls": [
            {
                "id": "permanent-transient-cache",
                "kind": "ttl-never-expires-on-transient",
                "description": (
                    "PermanentTransientCache stores a 503 with a 10^12s ttl. "
                    "After the honest short ttl would have expired the mutant "
                    "still serves from cache (no transport call). The honest "
                    "cache retries."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "pass": True,
            },
            {
                "id": "empty-cache-reports-ok",
                "kind": "empty-ok-status-mutant",
                "description": (
                    "empty_ok_mutant_status returns ok=true with entries=0. "
                    "The detector flags it; honest empty status is ok=false."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "pass": True,
            },
        ],
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "named_probes": [
            {
                "id": "probe1",
                "role": "second-attempt-observed-network-call",
                "command": P1,
            },
            {
                "id": "probe2",
                "role": "recorded-type-ttl-404-empty-ok-and-mutant",
                "command": P2,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0176-probe2-entry-type-ttl",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not reuse probe 1's transport call log. It "
                "re-reads on-disk type and ttl, re-runs the 404 full-ttl "
                "window, the empty-OK detector, and the permanent-transient "
                "mutant."
            ),
        },
        "cloud_ok": False,
        "registered": True,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": sut, "exists": True, "role": "fetch-cache-sut"},
            {
                "path": "command-center/p2-wave/probes/TST-0176/_validate_out.json",
                "exists": True,
                "role": "prior-estate-measurement",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "No production tools/*/cache.py with fetch/ttl was present "
                    "on this worktree at delivery. The named probes measure "
                    "the in-probe FetchCache, not a reconstructed ADV harness."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "an ADV rebuild was performed",
            ]
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out_path)
    if size < min_bytes:
        print(f"FAILED:TST-0176 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0176" not in text:
        print("FAILED:TST-0176 sentinel missing from file")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0176 self-declared blocked")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0176 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
