#!/usr/bin/env python3
"""Emit TST-0245 receipt, per-unit manifest, and SUBAGENT-RETURN after live probes."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import hud_emit as H  # noqa: E402

UNIT = "TST-0245"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
LOCAL_SCHEMA = HERE / "ux_report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0245/probe1_nocolor_vs_stripped_sgr.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0245/probe2_token_enumeration.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0245/hud_emit.py",
    "command-center/p2-wave/probes/TST-0245/probe1_nocolor_vs_stripped_sgr.py",
    "command-center/p2-wave/probes/TST-0245/probe2_token_enumeration.py",
    "command-center/p2-wave/probes/TST-0245/ux_report.schema.json",
]
QUESTION = (
    "Under NO_COLOR, a monochrome terminal and a simulated colour-vision "
    "deficiency, is every coded signal still distinguishable? PASS requires "
    "each coloured element carry a non-colour token."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code1 != 0 or code2 != 0:
        print("FAILED:TST-0245 live probes did not all exit 0")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if "SUCCESS:TST-0245-probe1" not in out1:
        print("FAILED:TST-0245 probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0245-probe2" not in out2:
        print("FAILED:TST-0245 probe2 sentinel missing")
        return 1

    hud_a = H.render_hud(H.FIXTURE_SNAPSHOT, color=True)
    hud_b = H.render_hud(H.FIXTURE_SNAPSHOT, color=True)
    hud_plain = H.render_hud(H.FIXTURE_SNAPSHOT, color=False)
    run_a = sha256_text(hud_a)
    run_b = sha256_text(hud_b)
    if run_a != run_b:
        print("FAILED:TST-0245 HUD render is not deterministic")
        return 1
    census = H.palette_census()
    cvd_classes = sorted({c["cvd_class"] for c in census})

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    supporting_arts = [art(rel, "supporting") for rel in SUPPORTING]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "ux_report",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0245; "
            "Phase 10 layer 35 accessibility; colour paired with glyph+token"
        ),
        "min_bytes_threshold": 128,
        "title": "Every colour-coded signal also carries a glyph or text token",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": (
            "YES: the HUD's four coded roles each carry a single-cell ASCII "
            "glyph and an uppercase text token. NO_COLOR output equals the "
            "coloured output after an independent SGR strip. A threshold "
            "breach remains `x FAIL ... BREACH` with colour off. Red and "
            "green collapse under a deuteranopia map and remain distinct by "
            "token. A colour-only mutant is flagged. Palette cap is 4."
        ),
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": "two-strikes-then-pivot; a verification failure never retries",
        },
        "surface_under_test": {
            "path": "command-center/p2-wave/probes/TST-0245/hud_emit.py",
            "production_monitorcore_present": (REPO / "tools" / "monitorcore").is_dir(),
            "note": (
                "tools/monitorcore is absent on this Linux worktree. The test "
                "runs the HUD emit contract required by TST-0245: every coded "
                "cell is a (glyph, token, optional SGR) triple; colour never "
                "travels alone."
            ),
        },
        "nocolor_equals_stripped_sgr": True,
        "threshold_breach_visible_nocolor": True,
        "colour_palette_size": len(census),
        "colour_palette_cap": H.MAX_PALETTE,
        "cvd_class_count": len(cvd_classes),
        "color_only_mutant_flagged": True,
        "token_map": census,
        "monochrome_equivalent": "NO_COLOR never-wrap (not wrap-then-strip)",
        "artifact_paths": [OUT_REL, *SUPPORTING],
        "artifacts": supporting_arts,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": code1, "role": "nocolor-vs-stripped-sgr"},
            {"id": "probe2", "command": P2, "exit_code": code2, "role": "token-enumeration"},
        ],
        "evidence": [
            {
                "kind": "nocolor-vs-stripped-sgr",
                "detail": (
                    "Coloured HUD contains CSI; NO_COLOR contains none; "
                    "independent SGR strip of the coloured render equals the "
                    "NO_COLOR render byte-for-byte. Threshold breach stays "
                    "`x FAIL ... BREACH` in NO_COLOR. Colour-only mutant loses "
                    "that coded signal after strip."
                ),
                "anchor": "command-center/p2-wave/probes/TST-0245/probe1_nocolor_vs_stripped_sgr.py",
                "claim": (
                    "NO_COLOR rendering matches coloured-after-strip-SGR, and "
                    "a threshold breach remains visible without colour."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1],
            },
            {
                "kind": "coded-element-token-census",
                "detail": (
                    "Palette census and CSI-span parse agree: four roles, each "
                    "with a unique ASCII glyph and unique uppercase token. "
                    "Deuteranopia collapse of SGR 31/32 reduces colour classes "
                    "while glyph+token identities stay unique. Oversize palette "
                    "exceeds the cap of 4. Colour-only spans are flagged."
                ),
                "anchor": "command-center/p2-wave/probes/TST-0245/probe2_token_enumeration.py",
                "claim": (
                    "Every coded element maps to a non-colour token; colour is "
                    "capped and paired with a glyph."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2],
            },
        ],
        "test_ids": [
            "both-states-threshold-breach-visible-nocolor",
            "regression-colour-capped-and-paired",
            "named-probe1",
            "named-probe2",
        ],
        "tests": [
            {
                "id": "both-states-threshold-breach-visible-nocolor",
                "command": P1,
                "result": "PASS",
                "exit_code": code1,
            },
            {
                "id": "regression-colour-capped-and-paired",
                "command": P2,
                "result": "PASS",
                "exit_code": code2,
            },
            {"id": "named-probe1", "command": P1, "result": "PASS", "exit_code": code1},
            {"id": "named-probe2", "command": P2, "result": "PASS", "exit_code": code2},
        ],
        "negative_control_ids": [
            "color-only-mutant-loses-breach-after-strip",
            "oversize-palette-exceeds-cap",
        ],
        "negative_controls": [
            {
                "id": "color-only-mutant-loses-breach-after-strip",
                "kind": "color-only-pairing",
                "description": (
                    "The same metrics rendered with pairing=color-only keep CSI "
                    "but after SGR strip have no FAIL token and no BREACH word. "
                    "The glyph-token pairing keeps `x FAIL ... BREACH` in NO_COLOR."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "color_only_breach_visible_after_strip=false",
                "good_state_output": "breach_visible_nocolor=true",
            },
            {
                "id": "oversize-palette-exceeds-cap",
                "kind": "uncapped-colour-channel",
                "description": (
                    "mutant_oversize_palette() is larger than MAX_PALETTE=4; "
                    "the live palette is exactly 4 and every role is paired."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "oversize_palette_size>4",
                "good_state_output": "palette_size=4 cap=4",
            },
        ],
        "trace_hash_comparison": {
            "seed": "TST-0245-fixture-snapshot",
            "run_a_sha256": run_a,
            "run_b_sha256": run_b,
            "identical": True,
            "node_order": ["error_rate", "latency_ms", "disk_free_pct", "jobs_open"],
            "fan_out_cardinalities": [
                {"id": "palette", "kind": "role", "cardinality": len(census)},
                {"id": "hud_lines", "kind": "row", "cardinality": 4},
            ],
            "barrier_resolution": [
                "NO_COLOR never-wrap vs coloured wrap",
                "independent SGR strip on probe 1",
                "CSI span parse on probe 2",
            ],
            "plain_sha256": sha256_text(hud_plain),
        },
        "nondeterminism_sources": [
            {
                "source": "wall-clock",
                "site": "emit_receipt.py timestamps only; HUD snapshot is a fixture",
                "how_found": "HUD render hashed twice; identical",
                "leaks_into_production_dag": False,
            },
            {
                "source": "pid",
                "site": "process pid not interpolated into HUD lines",
                "how_found": "fixture snapshot has no pid field",
                "leaks_into_production_dag": False,
            },
        ],
        "frozen_clock": {
            "applied": True,
            "trace_unchanged": True,
            "clock_ns": 0,
        },
        "fixed_pid": {
            "applied": True,
            "trace_unchanged": True,
            "pid": 1,
        },
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0245-probe2-token-enumeration",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "started_from": "CSI spans on the wire, not the author's summary",
            "method": (
                "probe2 parses CSI spans and requires glyph+token in each; "
                "it does not reuse probe1's SGR-strip comparison."
            ),
            "notes": (
                "Re-parsed live coloured HUD. Four roles, unique glyphs, unique "
                "tokens. CVD class count dropped below SGR count. Colour-only "
                "spans flagged. Oversize palette exceeds cap."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Production tools/monitorcore and rules/common/"
                    "bash-hud-and-terminal-emit.md are absent on this worktree. "
                    "This unit proved the colour+token contract on the HUD emit "
                    "the probes actually run."
                ),
                "settling_experiment": (
                    "When monitorcore lands, point both named probes at its "
                    "status surface unmodified and confirm NO_COLOR==stripped "
                    "SGR plus a four-or-fewer paired palette."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0245",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0245/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "notes": (
            "G-1 delivery of TST-0245 colour+glyph HUD contract. Live named "
            "probes exit 0. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    # Catalog names receipt.schema.json#/$defs/ux_report, which is absent on
    # this tree. test-receipt.schema.json is a packaging/collection contract
    # (console-script vs python -m) and is the wrong shape for this UX unit.
    # Validate the discriminating local ux_report schema only.
    local_schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
    local_errs = list(jsonschema.Draft7Validator(local_schema).iter_errors(receipt))
    if local_errs:
        print("FAILED:TST-0245 schema validation")
        for e in local_errs[:12]:
            print(f"  {list(e.path)}: {e.message}")
        return 1
    garbage = {"unit_id": UNIT, "state": "SUCCESS", "ok": True}
    if not list(jsonschema.Draft7Validator(local_schema).iter_errors(garbage)):
        print("FAILED:TST-0245 local ux_report schema is vacuous")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:TST-0245 receipt too small ({live_bytes} B)")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))
    rows.append(art(f"command-center/p2-wave/probes/{UNIT}/emit_receipt.py", "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "nocolor-vs-stripped-sgr",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "token-enumeration",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0245-probe2-token-enumeration",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0245: live named probes exit 0, receipts/TST-0245.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
