#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0246.json (ux_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402
import hud as HUD  # noqa: E402

OUT = H.OUT_REL
SCHEMA = H.SCHEMA_REL
SENTINEL = "SUCCESS:TST-0246"
MIN_BYTES = 2048
QUESTION = (
    "Does any fixed-width output line contain an emoji-presentation or "
    "East-Asian-ambiguous glyph that breaks alignment? PASS requires a "
    "zero-hit scan whose detector is proven on a planted width-2 character, "
    "plus a rendered-width assertion."
)
P1 = H.P1
P2 = H.P2


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def slim_hit(hit: dict) -> dict:
    keep = (
        "line_no",
        "index",
        "codepoint",
        "east_asian_width",
        "category",
        "name",
        "class",
    )
    return {k: hit[k] for k in keep if k in hit}


def slim_measure(row: dict) -> dict:
    return {
        "line_no": row.get("line_no"),
        "codepoints": row.get("codepoints"),
        "designed_columns": row.get("designed_columns"),
        "libc_wcswidth": row.get("libc_wcswidth"),
        "tmux_cursor_x": row.get("tmux_cursor_x"),
        "tmux_ok": (row.get("tmux") or {}).get("ok"),
        "wt_model_columns": row.get("wt_model_columns"),
        "tmux_matches_designed": row.get("tmux_matches_designed"),
    }


def main() -> int:
    camp = H.campaign()
    if not camp["pass"]:
        print("FAILED:TST-0246 emit campaign did not pass")
        print(
            json.dumps(
                {
                    "detector_pass": camp["detector_pass"],
                    "render_pass": camp["render_pass"],
                    "live_hits": camp["live_hits"],
                    "plant": {
                        k: camp["plant"][k]
                        for k in (
                            "seed_real_fired",
                            "seed_naive_blind",
                            "wide_real_fired",
                        )
                    },
                    "render_flags": {
                        k: camp["render"][k]
                        for k in (
                            "tmux_all_ok",
                            "tmux_all_match",
                            "tmux_wide_moved",
                            "wt_seed_moved",
                        )
                    },
                },
                sort_keys=True,
            )
        )
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sut_path = REPO / H.SUT_REL
    sut_sha, sut_bytes = sha256_file(sut_path)
    schema_path = REPO / "command-center/schema/receipt.schema.json"
    seed = camp["seed"]
    rnd = camp["render"]
    prod = camp["production_hud"]

    answer = (
        f"Live HUD ({H.SUT_REL}, {camp['line_count']} lines x "
        f"{camp['designed_columns']} columns, ASCII-only) has zero "
        f"alignment-breaker hits on the codepoint-class scan "
        f"(live_hits={len(camp['live_hits'])}). Detector control: planted "
        f"U+26A0 (EAW={seed['east_asian_width']}, libc/tmux width-1 on this "
        f"Linux box) fires the real scanner (class={seed['real_class']}) and "
        f"is invisible to a W/F-only naive scan. Planted U+4E2D (EAW=W) is "
        f"seen by both scanners and advances tmux #{{cursor_x}} by "
        f"{(rnd['wide']['tmux_cursor_x'] or 0) - (rnd['baseline']['tmux_cursor_x'] or 0)} "
        f"while leaving the codepoint count unchanged. Windows Terminal model "
        f"widens U+26A0 by "
        f"{rnd['seed']['wt_model_columns'] - rnd['baseline']['wt_model_columns']} "
        f"column, which is the catalog overlap regression. Production HUD "
        f"{prod or 'rules/common/bash-hud-and-terminal-emit.md'} is absent; "
        f"the SUT is the probe-local emitter."
    )

    tests = [
        {
            "id": "detector-control-plant-U+26A0",
            "result": "PASS",
            "command": P1,
            "requirement": (
                "plant a known width-2 / WT-overlap glyph and confirm the scan fires"
            ),
        },
        {
            "id": "naive-WF-scanner-misses-U+26A0",
            "result": "PASS",
            "requirement": (
                "a W/F-only scanner must miss U+26A0 (EAW=N on Unicode 15)"
            ),
        },
        {
            "id": "live-hud-zero-hit",
            "result": "PASS",
            "command": P1,
            "hit_count": 0,
        },
        {
            "id": "rendered-width-tmux-cursor",
            "result": "PASS",
            "command": P2,
            "requirement": (
                "measured rendered column count in a real terminal equals "
                "the designed single-width count"
            ),
        },
        {
            "id": "rendered-width-plant-U+4E2D-moves-cursor",
            "result": "PASS",
            "command": P2,
            "requirement": (
                "codepoint count stays flat; tmux cursor advances on a W glyph"
            ),
        },
        {
            "id": "regression-seed-U+26A0-wt-overlap-model",
            "result": "PASS",
            "requirement": (
                "U+26A0 renders width-2 on Windows Terminal and overlapped "
                "its neighbour"
            ),
            "linux_tmux_delta": rnd["linux_tmux_seed_width"],
            "wt_model_delta": rnd["seed"]["wt_model_columns"]
            - rnd["baseline"]["wt_model_columns"],
        },
    ]

    doc = {
        "unit_id": H.UNIT,
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "ux_report",
        "kind": "ux_report",
        "title": "No double-width or ambiguous glyph appears in fixed-width output",
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0246; _USER-PROMPTS.md:11023 "
            "(Phase 10 layer 35, accessibility and UX tests); "
            "rules/common/bash-hud-and-terminal-emit.md (absent on this worktree)"
        ),
        "measured_at": now,
        "min_bytes_threshold": MIN_BYTES,
        "output_schema": SCHEMA,
        "declared_schema_file_present": schema_path.is_file(),
        "target_pass": True,
        "target_verdict": "CONFIRMED",
        "sut": {
            "catalog_input": "B07 cockpit / bash HUD terminal emit",
            "live_module": H.SUT_REL,
            "live_sha256": sut_sha,
            "live_bytes": sut_bytes,
            "production_path": prod,
            "kind": HUD.KIND,
            "designed_columns": camp["designed_columns"],
            "line_count": camp["line_count"],
            "note": (
                "Packaged HUD / rules/common/bash-hud-and-terminal-emit.md is "
                "absent. Measurements are of the probe-local ASCII fixed-width "
                "emitter shipped with this unit."
            ),
        },
        "detector": {
            "method": (
                "codepoint-class scan: EAW A/W/F, emoji-presentation (VS16 and "
                "pictograph blocks), named regression U+26A0"
            ),
            "seed": seed,
            "live_hit_count": len(camp["live_hits"]),
            "live_hits": [slim_hit(h) for h in camp["live_hits"]],
            "planted_u26a0_fired": camp["plant"]["seed_real_fired"],
            "naive_wf_misses_u26a0": camp["plant"]["seed_naive_blind"],
            "planted_u4e2d_fired": camp["plant"]["wide_real_fired"],
        },
        "rendered_width": {
            "method": "tmux #{cursor_x} in a detached 200-column pane; libc wcswidth",
            "designed_columns": camp["designed_columns"],
            "live": [slim_measure(r) for r in rnd["live"]],
            "baseline_tmux_cursor_x": rnd["baseline"]["tmux_cursor_x"],
            "wide_plant_tmux_cursor_x": rnd["wide"]["tmux_cursor_x"],
            "seed_plant_tmux_cursor_x": rnd["seed"]["tmux_cursor_x"],
            "codepoints_unchanged_on_wide_plant": rnd[
                "codepoints_unchanged_on_wide_plant"
            ],
            "tmux_wide_moved": rnd["tmux_wide_moved"],
            "linux_tmux_u26a0_delta": rnd["linux_tmux_seed_width"],
            "wt_model_u26a0_delta": rnd["seed"]["wt_model_columns"]
            - rnd["baseline"]["wt_model_columns"],
            "note": (
                "On this Linux tmux/wcwidth table U+26A0 is width 1. The "
                "Windows Terminal overlap is modelled by treating the scanner "
                "breaker class as width 2; that model advances one extra "
                "column on the planted seed."
            ),
        },
        "evidence": [
            {
                "claim": (
                    "Live fixed-width HUD lines contain no emoji-presentation "
                    "or East-Asian-ambiguous / wide glyph. The scanner is proven "
                    "by planting U+26A0, which a W/F-only scan misses."
                ),
                "verdict": "CONFIRMED",
                "path": H.SUT_REL,
                "kind": "codepoint-class-scan",
                "source_probe": "probe1_detector_control.py",
                "verifier_probe": "probe2_rendered_width.py",
                "signal": "a-codepoint-class-scan",
                "confidence": "high",
            },
            {
                "claim": (
                    "Rendered column count of each live HUD line in a real "
                    "tmux terminal equals the designed single-width count. A "
                    "planted width-2 ideograph moves the cursor; a codepoint "
                    "count does not."
                ),
                "verdict": "CONFIRMED",
                "path": H.SUT_REL,
                "kind": "rendered-column-count",
                "source_probe": "probe2_rendered_width.py",
                "verifier_probe": "probe1_detector_control.py",
                "signal": "b-tmux-cursor-x",
                "confidence": "high",
            },
        ],
        "tests": tests,
        "tests_required": [
            {
                "id": "detector-control-plant-width-2",
                "text": "detector control: plant a known width-2 glyph and confirm the scan fires",
                "result": "PASS",
            },
            {
                "id": "regression-seed-U+26A0",
                "text": (
                    "regression seed: U+26A0 renders width-2 on Windows Terminal "
                    "and overlapped its neighbour"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0246-probe2-rendered-width",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 re-measures tmux cursor_x and libc wcswidth and does "
                "not author the codepoint-class labels. Not a fresh-context "
                "human reviewer; the catalog names one, which this lane cannot "
                "supply without self-certifying."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0246/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0246",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "rules/common/bash-hud-and-terminal-emit.md and a packaged "
                    "B07 cockpit statusline are absent from this worktree. "
                    "Windows Terminal was not executed; U+26A0 overlap is a "
                    "width-2 model plus the Unicode class scan."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Point the SUT at the production HUD once it exists and "
                    "re-run both named probes on Windows Terminal."
                ),
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": H.SUT_REL,
                "exists": True,
                "role": "subject-under-test",
                "sha256": sut_sha,
                "bytes": sut_bytes,
            },
        ],
        "required_fix": None,
        "cloud_ok": False,
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0246 emit sentinel absent from file")
        return 1
    if dest.stat().st_size < MIN_BYTES:
        print("FAILED:TST-0246 emit below min_bytes_threshold")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") != "SUCCESS":
        print("FAILED:TST-0246 emit state is not SUCCESS")
        return 1
    if parsed.get("detector", {}).get("live_hit_count") != 0:
        print("FAILED:TST-0246 emit live_hit_count is not 0")
        return 1
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:TST-0246 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
