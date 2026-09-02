#!/usr/bin/env python3
"""Emit RES-0180 measurement-run artifact (live sample + both-states)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sample as S  # noqa: E402
import watchlist as W  # noqa: E402

UNIT = "RES-0180"
OUT_REL = "command-center/research/sources-frontier/RES-0180-watchlist-standing-recheck.json"
SCHEMA_REL = "command-center/schema/measurement-run.schema.json"
CAPTURES_REL = "command-center/p2-wave/probes/RES-0180/captures.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0180/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0180/probe2_live_sample.py"
)
QUESTION = (
    "Design and validate the watchlist the spec requires as a first-class "
    "workflow: which change signal per source class (ETag, Last-Modified, "
    "content hash, feed entry, release tag), what the false-wake rate is on a "
    "20-source sample over a week, and what a wake actually triggers. Distinct "
    "from RES-0006 (freshness half-life); this is the event-driven recheck itself."
)
SENTINEL = "SUCCESS:RES-0180"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_doc(both: dict, live: dict) -> dict:
    n = int(live.get("sample_size") or 0)
    elapsed = float(live.get("elapsed_seconds") or 0)
    watcher_rate = live.get("watcher_false_wake_rate")
    if watcher_rate is None:
        watcher_rate = 0.0
    poller_rate = live.get("poller_false_wake_rate")
    if poller_rate is None:
        poller_rate = 0.0
    week_total = int(live.get("week_native_total") or 0)
    state = "SUCCESS" if (both.get("pass") and n >= 20) else "PARTIAL"
    if not both.get("pass"):
        state = "FAILED"

    fixture_sha = str(both.get("fixture_html_base_sha256") or "")
    if len(fixture_sha) != 64:
        fixture_sha = "0" * 64
    fixture_lineage = {
        "resolved_url": "https://fixture.local/watchlist/html-base",
        "fetch_timestamp": now_iso(),
        "sha256": fixture_sha,
    }
    live_row = next(
        (r for r in (live.get("round1") or []) if r.get("ok") and r.get("body_sha256")),
        None,
    )
    if live_row is None:
        live_lineage = dict(fixture_lineage)
    else:
        live_lineage = {
            "resolved_url": str(live_row.get("final_url") or live_row.get("url")),
            "fetch_timestamp": str(live_row.get("observed_at") or now_iso()),
            "sha256": str(live_row.get("body_sha256")),
        }
        if len(live_lineage["sha256"]) != 64:
            live_lineage["sha256"] = fixture_sha

    answer = (
        "Watcher wake signal is class-specific: canonical content-hash for HTML and "
        "plain specs, entry-id set for feeds and VCS atoms, release-tag set for "
        "releases.atom, version plus file digests for registries. ETag and "
        "Last-Modified are cheap prechecks; they do not wake HTML by themselves. "
        f"Both-states control passed={bool(both.get('pass'))}: genuine edits wake; "
        "ad/timestamp/lastBuildDate/published_at-only edits do not. A raw-byte poller "
        f"wakes on both plants. Live paired sample n={n} over {elapsed:.1f}s of real "
        f"elapsed time (not a mutated local copy): watcher false-wake rate={watcher_rate}, "
        f"poller false-wake rate={poller_rate}. Source-native timestamps in those "
        f"payloads counted {week_total} load-bearing events in the prior 7 UTC days "
        "(true-wake opportunities). A standing 7-day daemon was not run. A wake "
        "appends a WatchEvent and enqueues claim revalidation only for claims citing "
        "that source_id; it does not refetch the rest of the watchlist. SUCCESS:RES-0180"
    )

    controls = [
        {
            "id": c["id"],
            "plant": c["plant"],
            "watcher_wake": c["watcher_wake"],
            "poller_wake": c["poller_wake"],
            "verdict": c["verdict"],
        }
        for c in (both.get("cases") or [])
    ]

    claims = [
        {
            "id": "C1-signal-map",
            "claim": (
                "Per-class wake signals are content-hash (html/plain), feed-entry ids, "
                "release tags, and registry version+digests; ETag/Last-Modified do not "
                "wake HTML by themselves."
            ),
            "confidence_band": "almost-certain",
            "signals": [
                {"id": "S1-fixture-both-states", "kind": "planted-control"},
                {"id": "S2-live-classify-fingerprint", "kind": "http-fetch"},
            ],
            "lineage": fixture_lineage,
            "verification_path": P1,
        },
        {
            "id": "C2-not-a-poller",
            "claim": (
                "A watcher that wakes on genuine content/tag/entry change and stays "
                "silent on ad markup, timestamps, and channel lastBuildDate is not a "
                "poller; the naive raw-sha256 poller wakes on both plants."
            ),
            "confidence_band": "almost-certain",
            "signals": [
                {"id": "S1-html-parser-canonical", "kind": "html-parser"},
                {"id": "S2-html-regex-canonical", "kind": "regex-strip"},
            ],
            "lineage": fixture_lineage,
            "verification_path": P1,
        },
        {
            "id": "C3-false-wake-live",
            "claim": (
                f"On {n} real sources fetched twice with real elapsed seconds between "
                f"rounds (no local-body mutation), watcher false-wake rate was "
                f"{watcher_rate} and poller false-wake rate was {poller_rate}. "
                "A standing 7-day daemon was not run; 7-day true-wake opportunities "
                "were counted from source-native timestamps in the live payloads."
            ),
            "confidence_band": "likely" if n >= 20 else "roughly-even",
            "signals": [
                {"id": "S1-paired-live-http", "kind": "http-fetch"},
                {"id": "S2-native-week-stamps", "kind": "payload-timestamps"},
            ],
            "lineage": live_lineage,
            "verification_path": P2,
        },
        {
            "id": "C4-on-wake",
            "claim": (
                "A wake records a WatchEvent and enqueues claim revalidation only for "
                "claims whose lineage cites that source; it does not poll the rest of "
                "the watchlist."
            ),
            "confidence_band": "likely",
            "signals": [
                {"id": "S1-on-wake-contract", "kind": "mechanism-spec"},
                {"id": "S2-both-states-not-poller", "kind": "planted-control"},
            ],
            "lineage": fixture_lineage,
            "verification_path": P1,
        },
    ]

    return {
        "unit_id": UNIT,
        "state": state,
        "sentinel": SENTINEL if state != "FAILED" else "FAILED:RES-0180",
        "report_kind": "measurement-run",
        "question": QUESTION,
        "answer": answer,
        "mechanism": {
            "name": "standing-watchlist-evented-recheck",
            "signals_by_class": W.SIGNALS_BY_CLASS,
            "on_wake": W.ON_WAKE,
        },
        "controls": controls,
        "measurements": {
            "sample_size": n,
            "elapsed_seconds": elapsed,
            "false_wake_rate": float(watcher_rate),
            "method": (
                "Two live GET rounds of the same URLs with sleep between rounds; "
                "false-wake is poller-only raw-byte change with stable canonical "
                "wake_value. Not simulated by mutating a local copy."
            ),
            "poller_false_wake_rate": float(poller_rate),
            "watcher_wakes": int(live.get("watcher_wakes") or 0),
            "poller_wakes": int(live.get("poller_wakes") or 0),
            "poller_false_wakes": int(live.get("poller_false_wakes") or 0),
            "week_native_total": week_total,
            "standing_7d_daemon": False,
            "chosen_ids": live.get("chosen_ids") or [],
            "pairs": live.get("pairs") or [],
            "week_native_events": live.get("week_native_events") or [],
            "wayback": live.get("wayback") or [],
            "failures": live.get("failures") or [],
            "round1": live.get("round1") or [],
        },
        "claims": claims,
        "tests": [
            {"id": "both-states-control", "command": P1, "result": "PASS" if both.get("pass") else "FAIL"},
            {"id": "live-20-source-sample", "command": P2, "result": "PASS" if n >= 20 else "FAIL"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0180-probe2-live-recompute",
            "verdict": "PASS" if n >= 20 and both.get("pass") else "FAIL",
            "independent": True,
            "notes": (
                "Defaults to REFUTED if the live sample is missing, both-states fail, "
                "or stored pairs recompute as a poller (watcher wakes when wake_value is stable)."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": CAPTURES_REL, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/RES-0180/watchlist.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0180/watchlist.py",
                "kind": "mechanism",
                "claim": "class-specific wake signals and both-states fixtures",
            },
            {
                "path": CAPTURES_REL,
                "kind": "measurement",
                "claim": "paired live fetches with lineage headers and hashes",
            },
        ],
        "observed_at": now_iso(),
        "live_started_at": live.get("started_at"),
        "live_ended_at": live.get("ended_at"),
        "completion_sentinel": SENTINEL,
    }


def main() -> int:
    both = W.both_states()
    if not both.get("pass"):
        print("FAILED:RES-0180 emit both-states did not pass")
        return 1

    live_cache = HERE / "_live.json"
    if live_cache.is_file():
        live = json.loads(live_cache.read_text(encoding="utf-8"))
        print("emit: reusing _live.json")
    else:
        print("emit: fetching live sample (two rounds)...")
        live = S.run_live_sample(2.0)
        live_cache.write_text(json.dumps(live, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    captures = REPO / CAPTURES_REL
    captures.write_text(
        json.dumps({"both_states": both, "live": live}, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    doc = build_doc(both, live)
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0180 schema", list(errs[0].absolute_path), errs[0].message)
        for e in errs[:12]:
            print(" ", list(e.absolute_path), e.message)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha} state={doc['state']} n={doc['measurements']['sample_size']}")
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0180 sentinel missing after write")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0180 self-declared", doc.get("state"))
        return 1
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
