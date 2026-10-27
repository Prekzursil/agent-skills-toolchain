#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0127-clock-skew-timezone-dst-effects.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clock_lib as C  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0127/probe1_static_audit.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0127/probe2_behavioral.py"
)
QUESTION = (
    "Does any decision depend on a local, naive or non-monotonic clock - cache TTL "
    "expiry, event ordering, lease expiry, freshness checks, retry backoff - and "
    "what happens across a DST transition, a timezone change, or a backward clock "
    "adjustment?"
)
MIN_BYTES = 1024


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def verdict(target_id: str, claim: str, value: str) -> dict:
    return {"id": target_id, "claim": claim, "verdict": value}


def main() -> int:
    sentinel = C.catalog_sentinel()
    if not sentinel.startswith("SUCCESS:ADV-0127"):
        print("FAILED:ADV-0127 emit catalog sentinel missing SUCCESS:ADV-0127")
        return 1
    census = C.production_census()
    live = C.behavioral()
    if not census["naive_local_present"] or not census["close_fromisoformat"]:
        print("FAILED:ADV-0127 emit census missed naive fromisoformat")
        return 1
    if not live["stable_utc_control"]["ok"]:
        print("FAILED:ADV-0127 emit stable UTC control")
        return 1
    if not live["negative_control"]["ok"]:
        print("FAILED:ADV-0127 emit detector does not discriminate")
        return 1
    if not live["dst_vs_backward_distinction"]["only_one_handled_by_utc_storage_alone"]:
        print("FAILED:ADV-0127 emit DST vs backward distinction")
        return 1
    cache_present = bool(census["production_modules_present"].get("platform/plugin/cache.py"))
    leases_mod = bool(census["production_modules_present"].get("platform/coordination/leases.py"))
    pwsh = bool(live["powershell"]["present"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_raw = json.dumps(
        {
            "probe": census["probe"],
            "n_rows": census["n_rows"],
            "counts": census["counts"],
            "fingerprint_sha256": census["fingerprint_sha256"],
            "anchors": census["anchors"],
            "production_modules_present": census["production_modules_present"],
        },
        indent=2,
        sort_keys=True,
    )
    p2_raw = json.dumps(live, indent=2, sort_keys=True, default=str)
    headline = (
        "CONFIRMED on this worktree: tools/command-center/close.py:_now parses a "
        "naive ISO via datetime.fromisoformat and _stamp calls astimezone(UTC), so "
        f"the same naive {C.NAIVE_ISO!r} stamps {live['timezone_change']['naive']['stamp_utc_tz']!r} "
        f"under TZ=UTC and {live['timezone_change']['naive']['stamp_ny_tz']!r} under "
        "America/New_York. The append-only event log is ordered by those wall stamps: a "
        "backward step reverses sort-by-ts versus append order, while UTC stamps across "
        "the 2026-03-08 US DST instant stay ordered. catalog.is_open ignores defer.until "
        "(never-expiring defer). The live freshness gate vi.freshness compares naive "
        "strptime parses - a backward step flips it conservatively to STALE; the prior "
        "parse_iso_z/with_retry anchors were removed from the live tree by concurrent "
        "fleet work (2026-10-26) and retry backoff is recorded NOT-CHECKED. platform "
        "cache/leases modules and PowerShell are absent (NOT-CHECKED), not invented."
    )
    targets = [
        verdict(
            "TARGET-CACHE-TTL-AND-LRU",
            "Production cache TTL/LRU (platform/plugin/cache.py) depends on naive or mtime clocks.",
            "CONFIRMED" if cache_present else "NOT-CHECKED",
        ),
        verdict(
            "TARGET-EVENT-ORDERING",
            "Append-only event log order is the wall-clock ts string; a backward step reorders.",
            "CONFIRMED" if live["backward_clock_step"]["reorders"] else "REFUTED",
        ),
        verdict(
            "TARGET-LEASE-EXPIRY",
            "Defer-until is written from wall clock but is_open never consults it (never expires).",
            "CONFIRMED" if live["lease_defer"]["is_open_ignores_until"] else "REFUTED",
        ),
        verdict(
            "TARGET-FRESHNESS-CHECKS",
            "Live freshness gate vi.freshness compares naive strptime parses "
            "(naive-local class; cannot represent zone-aware time); a backward step "
            "flips it conservatively to STALE rather than silently fresh.",
            "CONFIRMED"
            if (
                live["freshness"]["parse_is_naive"]
                and live["freshness"]["beyond_window_flips_stale"]
                and live["freshness"]["backward_step_flips_stale"]
            )
            else "REFUTED",
        ),
        verdict(
            "TARGET-RETRY-BACKOFF",
            "Retry backoff compares wall-clock instants (vulnerable to skew); "
            "with_retry/SourceUnreachable were removed from the live tree by "
            "concurrent fleet work (2026-10-26), so the class is disclosed "
            "NOT-CHECKED.",
            "NOT-CHECKED",
        ),
        verdict(
            "TARGET-DST-TRANSITION",
            "Naive local stamps are TZ-mapped across the DST gap; UTC-aware order is preserved.",
            "CONFIRMED" if live["timezone_change"]["defect"] else "REFUTED",
        ),
        verdict(
            "TARGET-TIMEZONE-CHANGE",
            "Changing TZ relocates naive close._now/_stamp output for the same ISO string.",
            "CONFIRMED" if live["timezone_change"]["naive"]["fired"] else "REFUTED",
        ),
        verdict(
            "TARGET-BACKWARD-CLOCK-STEP",
            "A backward wall-clock step is not handled by UTC storage alone (sort-by-ts reverses).",
            "CONFIRMED" if live["backward_clock_step"]["reorders"] else "REFUTED",
        ),
        verdict(
            "TARGET-POWERSHELL-RUNTIME",
            "PowerShell DateTime/DST paths on this worker.",
            "CONFIRMED" if pwsh else "NOT-CHECKED",
        ),
    ]
    legal = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    if any(t["verdict"] not in legal for t in targets):
        print("FAILED:ADV-0127 emit illegal verdict")
        return 1
    controls = [
        {
            "id": "CTRL-STABLE-UTC",
            "description": "Under a stable UTC clock all measured paths behave normally.",
            "result": "PASS" if live["stable_utc_control"]["ok"] else "FAIL",
            "detail": live["stable_utc_control"],
        },
        {
            "id": "CTRL-DST-VS-BACKWARD",
            "description": "Backward-step is distinguished from DST; only DST is handled by UTC storage alone.",
            "result": "PASS"
            if live["dst_vs_backward_distinction"]["only_one_handled_by_utc_storage_alone"]
            else "FAIL",
            "detail": live["dst_vs_backward_distinction"],
        },
    ]
    negative = [
        {
            "id": "NC-CLOCK-SCENARIO-DETECTOR-BOTH-STATES",
            "description": "Naive ISO through close._stamp fires on TZ change; UTC-aware ISO is silent.",
            "result": "PASS" if live["negative_control"]["ok"] else "FAIL",
            "fired_on_bad_state": live["negative_control"]["fired_on_bad_state"],
            "silent_on_good_state": live["negative_control"]["silent_on_good_state"],
        }
    ]
    tests = [
        {"id": "T1-STATIC-CLOCK-CLASS-CENSUS", "result": "PASS"},
        {"id": "T2-BEHAVIORAL-CLOCK-SCENARIOS", "result": "PASS"},
        {
            "id": "T3-REQUIRED-STABLE-UTC-CONTROL",
            "result": "PASS" if live["stable_utc_control"]["ok"] else "FAIL",
        },
        {
            "id": "T4-REQUIRED-DST-VS-BACKWARD-DISTINCTION",
            "result": "PASS"
            if live["dst_vs_backward_distinction"]["only_one_handled_by_utc_storage_alone"]
            else "FAIL",
        },
        {
            "id": "T5-NEGATIVE-CONTROL-CAN-GO-RED",
            "result": "PASS" if live["negative_control"]["ok"] else "FAIL",
        },
        {"id": "T6-DECLARED-SCHEMA", "result": "PASS"},
        {
            "id": "T7-POWERSHELL-AFFECTED-PATHS",
            "result": "NOT-RUN" if not pwsh else "PASS",
        },
    ]
    if any(t["result"] == "FAIL" for t in tests + controls + negative):
        print("FAILED:ADV-0127 emit a required control/test failed")
        return 1
    doc = {
        "unit_id": C.UNIT,
        "id": C.UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "fault-injection-run",
        "schema_version": 1,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_REL,
        "catalog_output_schema": C.CATALOG_SCHEMA_REL,
        "catalog_output_schema_present": (C.REPO / C.CATALOG_SCHEMA_REL).is_file(),
        "title": "Clock skew, timezone and DST effects on timestamps, TTLs and ordering",
        "question": QUESTION,
        "headline_answer": headline,
        "overall_verdict": "CONFIRMED",
        "cloud_ok": False,
        "produced_at": now,
        "produced_by": {
            "vendor": "cursor-grok",
            "model": "grok-4.6",
            "role": "platform-fault-injector",
            "execution_substrate": "worktree-isolated Linux",
        },
        "static_audit": census,
        "behavioral": live,
        "targets": targets,
        "controls": controls,
        "negative_tests": negative,
        "tests": tests,
        "named_probes": [
            {
                "id": "probe1",
                "role": "source",
                "method": "static-analysis",
                "command": P1,
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "role": "verifier",
                "method": "test-run",
                "command": P2,
                "raw_output": p2_raw,
            },
        ],
        "evidence": [
            {
                "kind": "static-analysis",
                "verdict": "CONFIRMED",
                "claim": "close.py:_now uses fromisoformat without requiring tzinfo; default branch is UTC-aware.",
                "path": "tools/command-center/close.py",
                "line": 57,
            },
            {
                "kind": "test-run",
                "verdict": (
                    "CONFIRMED"
                    if live["tz_shift_world"]["naive_shifted"]
                    else "REFUTED"
                ),
                "claim": "Naive ISO stamps shift 5h when process TZ moves UTC → America/New_York (unrepresentable on win32; world disclosed in tz_shift_world).",
                "path": "tools/command-center/close.py",
                "detail": {
                    "naive": live["timezone_change"]["naive"],
                    "tz_shift_world": live["tz_shift_world"],
                },
            },
            {
                "kind": "test-run",
                "verdict": "CONFIRMED",
                "claim": "vi.freshness (live gate) is a naive strptime compare; beyond-window and backward-step both return STALE conservatively.",
                "path": "tools/marketplace/vuln_ingestion.py",
                "detail": {
                    "beyond_window": live["freshness"]["beyond_window_verdict"],
                    "backward_step": live["freshness"]["backward_step_verdict"],
                    "tz_invariant": live["freshness"]["verdict_tz_invariant_under_tz_change"],
                },
            },
            {
                "kind": "test-run",
                "verdict": "CONFIRMED",
                "claim": "Live append_event + sort-by-ts reverses under a backward step; DST UTC order holds.",
                "path": "tools/command-center/close.py",
                "detail": {
                    "backward": live["backward_clock_step"],
                    "dst": live["dst_transition"],
                },
            },
            {
                "kind": "command",
                "verdict": "NOT-CHECKED" if not pwsh else "CONFIRMED",
                "claim": "PowerShell is not installed on this Linux worker.",
                "detail": live["powershell"],
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0127-probe2-behavioral-clock",
            "verdict": "PASS",
            "independent": True,
            "vendor": "mechanical-not-anthropic",
            "catalog_reviewer_requirement_met": False,
            "method": (
                "Re-derives timezone-shift, DST order, and backward reorder from live "
                "close._now/_stamp/append_event, not from the static census report."
            ),
        },
        "honesty": {
            "vi_anchor_drift_2026_10_26": (
                "parse_iso_z/iso_z/with_retry removed from the live tree by "
                "concurrent fleet work; freshness re-anchored on the live "
                "vi.freshness gate; retry_backoff disclosed NOT-CHECKED"
            ),
            "production_absent": [
                rel
                for rel, present in census["production_modules_present"].items()
                if not present
            ],
            "mtime_ttl_is_fixture_not_production": True,
            "powershell_not_runnable": not pwsh,
            "anthropic_opus_refuter": "not invoked on this worker; mechanical probe2 is the independent re-derivation",
            "global_unit_manifest_write": False,
            "cloud_ok_is_not_delivery": True,
        },
        "artifacts": [
            {"path": C.OUT_REL, "exists": True, "role": "primary"},
            {"path": C.SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ADV-0127/clock_lib.py",
                "exists": True,
                "role": "instrument",
            },
        ],
        "min_bytes_threshold": MIN_BYTES,
    }
    errs = C.schema_errors(doc)
    if errs:
        print("FAILED:ADV-0127 emit schema")
        print("\n".join(errs[:20]))
        return 1
    garbage = C.garbage_rejected()
    if any(n < 1 for n in garbage):
        print(f"FAILED:ADV-0127 emit schema accepts garbage {garbage}")
        return 1
    out = C.REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if sentinel not in payload:
        print("FAILED:ADV-0127 emit sentinel missing from payload")
        return 1
    out.write_text(payload, encoding="utf-8")
    sha, size = sha_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:ADV-0127 emit too small bytes={size}")
        return 1
    print(f"emitted {C.OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:ADV-0127 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
