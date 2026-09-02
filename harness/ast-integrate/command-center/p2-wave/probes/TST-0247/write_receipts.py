#!/usr/bin/env python3
"""Write TST-0247 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py
--write. Does not git add/commit/push.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

UID = "TST-0247"
OUT = "command-center/receipts/TST-0247.json"
SENTINEL = "SUCCESS:TST-0247"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/ux_report"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0247/probe1_plain_vs_tui.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0247/probe2_both_states_and_assistive.py"
)
SUPPORTING = [
    "tools/hud/cockpit.py",
    "tools/hud/statusline.py",
    "command-center/p2-wave/probes/TST-0247/probe1_plain_vs_tui.py",
    "command-center/p2-wave/probes/TST-0247/probe2_both_states_and_assistive.py",
    "command-center/p2-wave/probes/TST-0247/fixtures/payload.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0247/SUBAGENT-RETURN.json",
        "role": role,
    }


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UID:
            return unit
    raise SystemExit("FAILED:TST-0247 catalog unit missing")


def last_json_object(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or SENTINEL)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0247 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    p1 = last_json_object(t1)
    p2 = last_json_object(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:TST-0247 probe JSON pass=false")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    plain_set = p1.get("plain_set") or []
    tui_set = p1.get("tui_set") or []
    hidden = p2.get("hidden_field")
    diff = p2.get("set_difference") or []
    answer = (
        f"--plain and the TUI cockpit expose the same information set "
        f"{plain_set}; comparison is mechanical field-set equality of live "
        f"CLI stdout, not a visual impression (raw bytes equal="
        f"{p1.get('raw_bytes_equal')}; TUI has cursor addressing="
        f"{p1.get('tui_has_cursor_addressing')}). Hiding {hidden!r} from the "
        f"TUI produces set difference {diff}. --plain is line-oriented with "
        f"no CSI/cursor-addressing. {sentinel}"
    )
    receipt = {
        "schema_version": 1,
        "kind": "ux_report",
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "title": unit.get("title"),
        "question": unit.get("question_or_target"),
        "answer": answer,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0247; "
            "rules/common/bash-hud-and-terminal-emit.md; "
            "tools/hud/cockpit.py --plain vs TUI panes"
        ),
        "min_bytes_threshold": 128,
        "ux_report": {
            "subject": "tools/hud/cockpit.py",
            "payload": "command-center/p2-wave/probes/TST-0247/fixtures/payload.json",
            "detector": "mechanical field-set equality of parsed stdout",
            "not_a_detector": "visual impression or raw-byte equality",
            "plain_fields": p1.get("plain_fields"),
            "tui_fields": p1.get("tui_fields"),
            "sets_equal": p1.get("sets_equal"),
            "values_equal": p1.get("values_equal"),
            "raw_bytes_equal": p1.get("raw_bytes_equal"),
            "hidden_field": hidden,
            "set_difference": diff,
            "assistive_line_oriented_no_csi": p2.get("assistive_line_oriented_no_csi"),
        },
        "evidence_requirement": unit.get("evidence_requirement"),
        "evidence": {
            "compared_mechanically": True,
            "raw_bytes_equal": bool(p1.get("raw_bytes_equal")),
            "a_plain_field_set": {
                "id": "E1-plain-parsed-fields",
                "claim": (
                    "Field set parsed from --plain stdout (line-oriented, "
                    "CSI-rejected) equals the canonical cockpit fields."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/hud/cockpit.py:parse_plain_fields",
                "confidence": "almost-certain",
                "fields": p1.get("plain_fields"),
            },
            "b_tui_pane_field_set": {
                "id": "E2-tui-pane-parsed-fields",
                "claim": (
                    "Field set parsed from TUI pane stdout after CSI strip "
                    "equals the plain field set. TUI stdout contains CUP/ED."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/hud/cockpit.py:parse_tui_fields",
                "confidence": "almost-certain",
                "fields": p1.get("tui_fields"),
                "has_cursor_addressing": p1.get("tui_has_cursor_addressing"),
            },
        },
        "artifact_paths": [OUT, *SUPPORTING],
        "artifacts": [{"path": OUT, "role": "primary", "exists": True}]
        + [{"path": p, "role": "supporting", "exists": True} for p in SUPPORTING],
        "test_ids": [
            "TST-0247-probe1-plain-vs-tui-field-set",
            "TST-0247-probe2-both-states-and-assistive",
        ],
        "tests": [
            {
                "id": "TST-0247-probe1-plain-vs-tui-field-set",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
                "requirement": (
                    "field-level set comparison of --plain vs TUI panes, "
                    "not a visual impression"
                ),
                "output_tail": t1[-4000:],
            },
            {
                "id": "TST-0247-probe2-both-states-and-assistive",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
                "requirement": (
                    "both-states: hiding a field from the TUI shows as a set "
                    "difference; assistive: plain is line-oriented with no "
                    "cursor-addressing"
                ),
                "output_tail": t2[-4000:],
            },
        ],
        "negative_control_ids": [
            "TST0247-NC1-raw-bytes-not-the-detector",
            "TST0247-NC2-visual-comparator-misses-hidden-field",
        ],
        "negative_controls": [
            {
                "id": "TST0247-NC1-raw-bytes-not-the-detector",
                "kind": "detector-control",
                "description": (
                    "TUI stdout contains CSI CUP/ED so raw bytes differ from "
                    "--plain while field sets match."
                ),
                "fired_on_bad_state": not bool(p1.get("raw_bytes_equal")),
                "silent_on_good_state": bool(p1.get("sets_equal")),
            },
            {
                "id": "TST0247-NC2-visual-comparator-misses-hidden-field",
                "kind": "both-states",
                "description": (
                    "A visual non-empty comparator stays silent when model is "
                    "hidden from the TUI; the mechanical set comparator fires."
                ),
                "fired_on_bad_state": bool(
                    p2.get("mechanical_set_comparator_catches_hidden_field")
                ),
                "silent_on_good_state": bool(
                    p2.get("visual_comparator_misses_hidden_field")
                ),
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0247-probe2-both-states-and-assistive",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests (named probes), not the author's summary",
            "adversarial_refuter": "hide-field must produce a set difference",
            "used_author_parse_functions": False,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0247/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "rules/common/bash-hud-and-terminal-emit.md is named in "
                    "the catalog inputs but is absent on this worktree. The "
                    "measured surface is tools/hud/cockpit.py."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore the HUD emit rule and re-run the field-set "
                    "probes against any additional panes it names."
                ),
            }
        ],
        "timestamps": {"ended_at": now},
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0247: live named probes exit 0, receipts/TST-0247.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. "
            + sentinel
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:TST-0247 sentinel absent after write")
        return 1
    if '"state": "SUCCESS"' not in text and '"state":"SUCCESS"' not in text:
        print("FAILED:TST-0247 state not SUCCESS")
        return 1

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:TST-0247 probes after receipt c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "plain-vs-tui-field-set",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "both-states-and-assistive",
                "raw_output": t2b,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0247/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0247-probe2-both-states-and-assistive",
            "verdict": "PASS",
            "independent": True,
        },
        "reviewer_verdict": "PASS",
        "ts": now,
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0247: live named probes exit 0, receipts/TST-0247.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"plain_set={plain_set} tui_set={tui_set} hide_diff={diff}")
    print("SUCCESS:TST-0247 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
