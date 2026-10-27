#!/usr/bin/env python3
"""ADV-0127 wave-4 re-anchor: dead vi anchors -> live freshness gate.

The live tree drifted again after the 2026-10-24 refresh: concurrent fleet
work removed parse_iso_z / iso_z / with_retry from
tools/marketplace/vuln_ingestion.py and added a naive-strptime freshness()
gate. This patch:
  1. classifies datetime.strptime as naive-local in the census detector,
  2. re-anchors behavioral() on the live vi.freshness()/now_iso() paths,
  3. discloses retry_backoff as NOT-CHECKED (anchor removed from live tree).
Probe semantics otherwise unchanged; probe2's retry assertion is updated by
the companion edit.
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "command-center" / "p2-wave" / "probes" / "ADV-0127" / "clock_lib.py"
src = P.read_text(encoding="utf-8")

# 1. classify_call: add strptime rule (live freshness gate parses naive)
old_rule = '''    if name == "getmtime":
        return "naive-local", "os.path.getmtime"'''
new_rule = '''    if name == "getmtime":
        return "naive-local", "os.path.getmtime"
    if name == "strptime":
        return (
            "naive-local",
            "datetime.strptime (naive result unless %z in format)",
        )'''
assert old_rule in src, "classify anchor missing"
src = src.replace(old_rule, new_rule, 1)

# 2. behavioral: replace dead vi anchors with live freshness-gate scenarios
old_block = '''        parse_naive = vi.parse_iso_z("2026-03-08T01:30:00")
        parse_z = vi.parse_iso_z("2026-03-08T01:30:00Z")
        guard.set("America/New_York")
        iso_z_naive_ny = vi.iso_z(datetime(2026, 3, 8, 1, 30, 0))
        guard.set("UTC")
        iso_z_naive_utc = vi.iso_z(datetime(2026, 3, 8, 1, 30, 0))
        delays: list[float] = []

        def boom() -> None:
            raise OSError("adv0127-retry")

        try:
            vi.with_retry(boom, max_attempts=3, rng=random.Random(0), sleep=delays.append)
            retry_exhausted = False
        except vi.SourceUnreachable:
            retry_exhausted = True
'''
new_block = '''        # Live production freshness gate (vi.freshness in
        # tools/marketplace/vuln_ingestion.py). Re-anchored 2026-10-26: the
        # prior anchors (parse_iso_z / iso_z / with_retry) were removed from
        # the live tree by concurrent fleet work; this block exercises the
        # gate that now carries the production freshness decision.
        def _v(queried_at: str) -> dict[str, Any]:
            purl = "pkg:npm/lodash@4.17.20"
            return {
                "status": vi.Status.CLEAN.value,
                "purl": purl,
                "queried_at": queried_at,
                "input_hash": vi.input_hash(purl, queried_at),
            }

        def _zulu_diff(a: str, b: str) -> float:
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            return abs(
                (
                    datetime.strptime(a, fmt) - datetime.strptime(b, fmt)
                ).total_seconds()
            )

        guard.set("UTC")
        fresh_zero_age = vi.freshness(
            _v("2026-08-09T12:00:00Z"), now="2026-08-09T12:00:00Z"
        )
        fresh_in_window = vi.freshness(
            _v("2026-08-09T11:00:00Z"), now="2026-08-09T12:00:00Z"
        )
        stale_beyond_window = vi.freshness(
            _v("2026-08-08T00:00:00Z"), now="2026-08-09T12:00:00Z"
        )
        stale_backward_step = vi.freshness(
            _v("2026-08-09T12:00:00Z"), now="2026-08-09T10:00:00Z"
        )
        guard.set("America/New_York")
        fresh_under_ny = vi.freshness(
            _v("2026-08-09T12:00:00Z"), now="2026-08-09T12:00:00Z"
        )
        now_iso_ny = vi.now_iso()
        guard.set("UTC")
        now_iso_utc = vi.now_iso()
        tampered = _v("2026-08-09T12:00:00Z")
        tampered["input_hash"] = "0" * 64
        stale_tampered_hash = vi.freshness(tampered, now="2026-08-09T12:00:00Z")
'''
assert old_block in src, "behavioral anchor missing"
src = src.replace(old_block, new_block, 1)

# 3. return-dict freshness block
old_fresh = '''        "freshness": {
            "parse_iso_z_naive_tzinfo": None if parse_naive.tzinfo is None else str(parse_naive.tzinfo),
            "parse_iso_z_zulu_aware": parse_z.tzinfo is not None,
            "iso_z_naive_ny": iso_z_naive_ny,
            "iso_z_naive_utc": iso_z_naive_utc,
            "iso_z_naive_shifts_with_tz": iso_z_naive_ny != iso_z_naive_utc,
        },'''
new_fresh = '''        "freshness": {
            "gate": "vi.freshness",
            "gate_path": "tools/marketplace/vuln_ingestion.py",
            "anchor_note": (
                "re-anchored 2026-10-26 on the live freshness gate; the prior "
                "parse_iso_z/iso_z anchors were removed from the live tree by "
                "concurrent fleet work"
            ),
            "parse_is_naive": True,
            "window_zero_age_verdict": fresh_zero_age,
            "window_in_window_verdict": fresh_in_window,
            "beyond_window_verdict": stale_beyond_window,
            "beyond_window_flips_stale": stale_beyond_window == vi.Status.STALE.value,
            "backward_step_verdict": stale_backward_step,
            "backward_step_flips_stale": stale_backward_step == vi.Status.STALE.value,
            "tampered_hash_verdict": stale_tampered_hash,
            "verdict_tz_invariant_under_tz_change": fresh_under_ny == fresh_zero_age,
            "naive_compare_cannot_represent_tz": True,
            "now_iso_utc": now_iso_utc,
            "now_iso_ny": now_iso_ny,
            "now_iso_format_zulu": bool(now_iso_utc.endswith("Z") and now_iso_ny.endswith("Z")),
            "now_iso_tz_invariant_within_5s": _zulu_diff(now_iso_utc, now_iso_ny) <= 5.0,
        },'''
assert old_fresh in src, "freshness return anchor missing"
src = src.replace(old_fresh, new_fresh, 1)

# 4. return-dict retry_backoff block -> disclosed NOT-CHECKED
old_retry = '''        "retry_backoff": {
            "clock_independent": True,
            "exhausted": retry_exhausted,
            "recorded_delays": delays,
            "uses_sleep_not_wall_compare": True,
        },'''
new_retry = '''        "retry_backoff": {
            "status": "NOT-CHECKED",
            "clock_independent": None,
            "reason": (
                "tools/marketplace/vuln_ingestion.py no longer exports "
                "with_retry/SourceUnreachable - the retry path was removed from "
                "the live tree by concurrent fleet work (observed 2026-10-26). "
                "No wall-clock-comparing retry backoff remains in the live tree "
                "to exercise; the class is disclosed NOT-CHECKED rather than "
                "asserted from a removed anchor."
            ),
        },'''
assert old_retry in src, "retry return anchor missing"
src = src.replace(old_retry, new_retry, 1)

P.write_text(src, encoding="utf-8", newline="\n")
print("clock_lib.py patched OK")
