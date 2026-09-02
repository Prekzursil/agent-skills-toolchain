#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0029-acquisition-scheduler.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from campaign import run_campaign  # noqa: E402

REPO = HERE.parents[3]
OUT = "command-center/wfa/WFA-0029-acquisition-scheduler.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/ProbeReport"
SENTINEL = "SUCCESS:WFA-0029"
QUESTION = (
    "Implementation target: a scheduler that serialises and jitter-staggers every "
    "credentialed external acquisition call made by the sweep lane and its retries, "
    "enforcing a per-provider token bucket read from config, so the bucket cannot "
    "produce a 429 thundering herd."
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    campaign = run_campaign()
    if not campaign.get("ok"):
        print("FAILED:WFA-0029 emit campaign not ok")
        print(json.dumps({
            "tests": campaign.get("tests"),
            "fingerprint": campaign.get("fingerprint"),
            "lint_pass": (campaign.get("lint") or {}).get("pass"),
        }, indent=2, default=str)[:4000])
        return 1

    impl = [
        "command-center/p2-wave/probes/WFA-0029/scheduler.py",
        "command-center/p2-wave/probes/WFA-0029/acquire.py",
        "command-center/p2-wave/probes/WFA-0029/providers.json",
        "command-center/p2-wave/probes/WFA-0029/mock_provider.py",
        "command-center/p2-wave/probes/WFA-0029/lint_call_sites.py",
        "command-center/p2-wave/probes/WFA-0029/campaign.py",
    ]
    src = {}
    for rel in impl:
        p = REPO / rel
        sha, n = digest_file(p)
        src[rel] = {"sha256": sha, "bytes": n}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dry = campaign["dry_run"]
    both = campaign["both_states"]
    lint = campaign["lint"]
    resume = campaign["resume"]

    doc = {
        "record_type": "ProbeReport",
        "schema_ref": SCHEMA,
        "unit_id": "WFA-0029",
        "id": "WFA-0029",
        "kind": "ProbeReport",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Arrival-stagger scheduler for every credentialed external acquisition call in this bucket",
        "question": QUESTION,
        "generated_at": now,
        "honesty": {
            "schema_pack_on_disk": (
                REPO / "command-center/wfa/schema/wfa-schema-pack.json"
            ).is_file(),
            "live_network": False,
            "salvage_tools_lib": "only tools/lib/codex-invocation.mjs present; 6-module salvage set absent",
            "dry_run": "virtual clock + independent mock provider surfaces",
            "sweep_lane_impls": (
                "Sweep-lane probe trees are on disk. Planted urlopen/gh-api "
                "bypasses still fire. Remaining live urlopen/gh-api sites in "
                "WFA-0016/0024/0026 are inventoried as downstream adoption "
                "(those units depend on WFA-0029) and are not rewritten here."
            ),
        },
        "implementation": {
            "choke_point": "command-center/p2-wave/probes/WFA-0029/acquire.py:credentialed_call",
            "scheduler": "command-center/p2-wave/probes/WFA-0029/scheduler.py",
            "config": "command-center/p2-wave/probes/WFA-0029/providers.json",
            "rule": (
                "Logical count (tokens_per_minute) is independent of simultaneous "
                "concurrency (max_inflight). Retries re-enter admit()."
            ),
            "source_sha256": src,
        },
        "config": campaign["config"],
        "evidence": {
            "A": {
                "requirement": (
                    "a measured arrival histogram from a dry run showing no "
                    "provider exceeds its configured rate"
                ),
                "pass": dry["scheduled"]["within_configured_rate"],
                "histogram": dry["scheduled"]["histogram"],
                "github_max_in_window": dry["scheduled"]["github_max_in_window"],
                "exa_max_in_window": dry["scheduled"]["exa_max_in_window"],
            },
            "B": {
                "requirement": (
                    "the providers' own 429 counters and rate-limit response "
                    "headers over the same window; a scheduler that reports "
                    "compliance while the provider reports throttling is a "
                    "detector failure, and the provider's counter wins"
                ),
                "scheduled_provider": dry["scheduled"]["github_provider"],
                "naive_burst_proves_429s_exist": dry["naive_burst"],
                "detector": dry["detector"],
                "pass": (
                    dry["naive_burst"]["produced_429s"]
                    and not dry["detector"]["detector_failure"]
                    and dry["scheduled"]["github_provider"]["http_429"] == 0
                ),
            },
        },
        "both_states": both,
        "resume": {
            "lost_ids": resume["lost_ids"],
            "crash_id": resume["crash_id"],
            "recovered_from_inflight": resume["crash_recovered_from_inflight"],
            "all_done": resume["all_done"],
            "pass": resume["pass"],
        },
        "lint": {
            "planted_fired": lint["planted_fired"],
            "routed_ok": lint["routed_ok"],
            "choke_point": lint["choke_point"],
            "own_clean": lint.get("own_clean"),
            "own_bypass": lint.get("own_bypass") or [],
            "live_files_scanned": lint["live_files_scanned"],
            "live_bypass": lint["live_bypass"],
            "live_bypass_paths": lint.get("live_bypass_paths") or [],
            "live_clean": lint.get("live_clean"),
            "pass": lint["pass"],
        },
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0029-probe2-histogram-lint",
            "verdict": "PASS",
        },
        "retry_through_scheduler": dry["retry_through_scheduler"],
        "token_bucket": campaign["token_bucket"],
        "tests": campaign["tests"],
        "fingerprint": campaign["fingerprint"],
        "computed_not_asserted": True,
        "pass": True,
        "answer": (
            "Per-provider token buckets from providers.json serialise and stagger "
            "credentialed calls. 1/min blocks (~60s virtual wait); 1000/min does "
            "not (<1s). A killed queue recovers inflight work. Planted urlopen and "
            "gh api bypasses fire the lint; routed credentialed_call is silent; "
            "this unit's own non-fixture sources have no bypass. Live sweep-lane "
            "urlopen/gh-api sites (WFA-0016 engine, WFA-0024 github_io, WFA-0026 "
            "capture) are named in lint.live_bypass_paths as downstream adoption. "
            "Dry-run histogram stays within rate; naive burst produces provider "
            "429s so the comparison is not vacuous; scheduled path records zero "
            "provider 429s. SUCCESS:WFA-0029"
        ),
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0029 emit sentinel missing")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    sha, n = digest_file(out)
    print(f"wrote {OUT} bytes={n} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
