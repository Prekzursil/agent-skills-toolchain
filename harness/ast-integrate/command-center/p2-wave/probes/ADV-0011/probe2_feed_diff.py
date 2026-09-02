#!/usr/bin/env python3
"""Probe 2: unversioned OSV package feed-diff for gates that cannot be re-executed.

Mechanically different from probe 1 (OSV versioned querybatch): this probe
asks osv.dev/v1/query with a package and no version whether any advisory
touching the dependency set exists, then diffs publication dates against
the stored-green timestamp. Requires the feed to fire on lodash while
staying silent on bytes. GitHub Advisory REST is not used (403 rate-limit
on this worktree made that instrument fail remesure with probe-exit:1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / E.OUT_REL
SENTINEL = (
    "SUCCESS:ADV-0011 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0011 <reason>."
)


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0011-probe2 {msg}")
    return 1


def main() -> int:
    live = E.investigate()
    payload = E.compact_probe2(live)
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"lodash_feed={payload['lodash']['n_feed']} "
        f"bytes_feed={payload['bytes']['n_feed']} "
        f"both_states={payload['feed_live_both_states']} "
        f"verdict={payload['target_verdict']}"
    )

    if payload["lodash"].get("error"):
        return fail(f"osv-lodash:{payload['lodash']['error']}")
    if payload["bytes"].get("error"):
        return fail(f"osv-bytes:{payload['bytes']['error']}")
    if not payload["feed_live_both_states"]:
        return fail("feed-not-live-or-not-both-states")
    if (payload["lodash"]["n_feed"] or 0) < 1:
        return fail("lodash-feed-empty")
    if (payload["bytes"]["n_feed"] or 0) != 0:
        return fail("bytes-feed-not-silent")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if SENTINEL not in text:
        return fail("catalog-sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    art_feed = ((doc.get("probe2") or {}).get("compact")) or {}
    art_lodash_n = art_feed.get("lodash", {}).get("n_feed") or 0
    art_bytes_n = art_feed.get("bytes", {}).get("n_feed")
    # Live advisory cardinality can move by one between emit and re-run; both
    # sides must still show lodash hits and bytes silence (both-states).
    if art_lodash_n < 1 or (payload["lodash"]["n_feed"] or 0) < 1:
        return fail(
            f"lodash-feed-empty live={payload['lodash']['n_feed']} art={art_lodash_n}"
        )
    if art_bytes_n not in {0, None} or (payload["bytes"]["n_feed"] or 0) != 0:
        return fail(
            f"bytes-not-silent live={payload['bytes']['n_feed']} art={art_bytes_n}"
        )
    if art_feed.get("feed_live_both_states") is not True:
        return fail("artifact-feed-both-states")
    live_t = next(
        t["verdict"]
        for t in live["targets"]
        if t["id"] == "advisory-feed-diff-for-unrerunnable-gates"
    )
    art_t = next(
        t["verdict"]
        for t in (doc.get("enumerated_targets") or [])
        if t.get("id") == "advisory-feed-diff-for-unrerunnable-gates"
    )
    if live_t != art_t:
        return fail(f"feed-target-drift live={live_t} art={art_t}")

    # Probe 2 must not be a copy of probe 1's instrument.
    p1_cmd = ""
    p2_cmd = ""
    for p in doc.get("named_probes") or []:
        if p.get("id") == "probe1":
            p1_cmd = p.get("command") or ""
        if p.get("id") == "probe2":
            p2_cmd = p.get("command") or ""
    if not p1_cmd or not p2_cmd or p1_cmd == p2_cmd:
        return fail("probes-not-mechanically-different")
    if "probe2_feed_diff" not in p2_cmd:
        return fail("probe2-command")
    print("SUCCESS:ADV-0011-probe2 OSV unversioned feed-diff matched artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
