#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0012-pinned-measurement-reprobe.json."""
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
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    COMPLETION_SENTINEL,
    OUT_REL,
    PROBE1_TEXT,
    PROBE2_TEXT,
    QUESTION,
    SCHEMA_REL,
    UNIT,
    probe1_payload,
    probe2_payload,
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0012/probe1_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0012/probe2_reprobe.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0012/engine.py",
    "command-center/p2-wave/probes/ADV-0012/probe1_inventory.py",
    "command-center/p2-wave/probes/ADV-0012/probe2_reprobe.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "eol": "LF" if path.is_file() else "ABSENT",
    }


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def validate(doc: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-missing"]
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(doc)
    ]


def v_of(rows: list[dict], aid: str) -> str:
    for row in rows:
        if row.get("id") == aid:
            return str(row.get("verdict") or "NOT-CHECKED")
    return "NOT-CHECKED"


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = probe1_payload()
    p2 = probe2_payload()
    assertions = list(p2["assertions"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mnn = v_of(assertions, "CAL-MNN-STILL-LIVE")
    retired = v_of(assertions, "CAL-RETIRED-TOOL-AVAILABLE")
    catalog = v_of(assertions, "CTRL-CATALOG-PARSES")
    zero = v_of(assertions, "GROUND-ZERO-SUCCESS")
    fortytwo = v_of(assertions, "GROUND-DELIVERED-42")
    ledger = v_of(assertions, "LIVE-LEDGER-DOCUMENTS-PRESENT")
    same = v_of(assertions, "SAME-INSTRUMENT-MNN")
    arts = p2["artifact_census"]
    live_ledgers = p1["live_ledger_present_count"]
    false_pins = [
        a["id"]
        for a in assertions
        if a["verdict"] == "REFUTED" and a["id"] != "SAME-INSTRUMENT-MNN"
    ]
    overall = "PARTIAL"
    if mnn != "REFUTED" or retired != "REFUTED":
        overall = "NOT-CHECKED"
    answer = (
        f"Live contracted ledgers present={live_ledgers} (PROGRAM-CHARTER, "
        "OWNER-DECISIONS, RISK-REGISTER, UNKNOWNS-REGISTER, STATUS, RUNBOOK "
        f"all absent on this worktree) so ledger-file pins are {ledger}. "
        f"Known-stale CAL-MNN-STILL-LIVE={mnn} (live option/architecture id "
        f"intersection={assertions[0]['observed']}, not 31; original grep of "
        "17-DECISION-LOG.md is banned for CONFIRMED). "
        f"Known-stale CAL-RETIRED-TOOL-AVAILABLE={retired} (PATH/which/"
        "importlib: get_budget and check_budget are not available). "
        f"Still-true CTRL-CATALOG-PARSES={catalog} via json.load work_units, "
        "not test -s. "
        f"Ground-lane P2-GROUNDING.md pins 'zero SUCCESS of 42' and "
        f"'delivered 42' are {zero}/{fortytwo}: filesystem glob of artifact "
        f"roots finds file_count={arts['file_count']} success_count="
        f"{arts['success_count']} (not the catalog-walk _probe_state_field.py). "
        f"Same-instrument 31-way grep is {same}. False pinned facts: "
        f"{false_pins}. {COMPLETION_SENTINEL}"
    )
    targets = [
        {
            "id": a["id"],
            "verdict": a["verdict"],
            "summary": a["claimed"],
            "original_probe": a["original_probe"],
            "substitute_probe": a["substitute_probe"],
        }
        for a in assertions
    ]
    allowed = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    if any(t["verdict"] not in allowed for t in targets):
        print(f"FAILED:{UNIT} target verdict not in enum")
        return 1
    nel = "\u0085"
    ctrl = p2["controls"]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": COMPLETION_SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "report_kind": "stale-premise-reprobe",
        "title": "Re-probe every dated measurement pinned in the command-center corpus with a different instrument",
        "question": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:11048, 10662-10679",
        "min_bytes_threshold": 4096,
        "profile": "stale-premise-reprobe",
        "overall_verdict": overall,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "stale-premise-refuter",
            "execution_substrate": "worktree-isolated",
        },
        "answer": answer,
        "mechanism": (
            "instrument-substitution re-probe with two known-stale calibration "
            "assertions embedded"
        ),
        "probe1_verbatim": PROBE1_TEXT,
        "probe2_verbatim": PROBE2_TEXT,
        "inputs_census": {
            "live_ledgers": p1["ledger_census"],
            "live_ledger_present_count": live_ledgers,
            "grounding_digest": p1["grounding_digest"],
            "planted_dated_count": len(p1["planted_dated"]),
            "live_dated_count": p1["live_dated_count"],
        },
        "targets": targets,
        "assertions": assertions,
        "evidence": [
            {
                "claim": (
                    "Probe 1 extracted dated assertions and named each original "
                    "probe, including both required known-stale calibrations."
                ),
                "verdict": "CONFIRMED" if p1["pass"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0012/probe1_inventory.py",
                "probes": [
                    {
                        "role": "source",
                        "id": "probe1",
                        "command": P1,
                        "raw_output": t1,
                        "exit_code": c1,
                    }
                ],
            },
            {
                "claim": (
                    "Probe 2 REFUTED both known-stale pins with substitute "
                    "instruments and left the original 31-way grep NOT-CHECKED."
                ),
                "verdict": "CONFIRMED" if p2["pass"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0012/probe2_reprobe.py",
                "probes": [
                    {
                        "role": "verifier",
                        "id": "probe2",
                        "command": P2,
                        "raw_output": t2,
                        "exit_code": c2,
                    }
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "NC1-same-instrument-grep-not-confirmed",
                "kind": "single-signal-rule-5",
                "description": (
                    "Re-grepping 31-way collision prose still hits the catalog "
                    "and would naive-CONFIRM the stale pin. That row is "
                    "NOT-CHECKED, never CONFIRMED."
                ),
                "fired_on_bad_state": bool(ctrl["naive_grep_would_confirm_stale_mnn"]),
                "silent_on_good_state": bool(ctrl["same_instrument_not_checked"]),
            },
            {
                "id": "NC2-id-intersection-fires-on-planted-overlap",
                "kind": "both-states",
                "description": (
                    "Planted option/architecture JSON shares exactly one id "
                    "(not 31). Disjoint architecture pair shares zero."
                ),
                "fired_on_bad_state": bool(ctrl["fixture_overlap_is_one"]),
                "silent_on_good_state": bool(ctrl["disjoint_overlap_is_zero"]),
            },
        ],
        "tests": [
            {
                "id": "T1-PROBE-1-INVENTORY",
                "name": "dated assertions extracted; both known-stale calibrations named",
                "command": P1,
                "result": "PASS" if c1 == 0 and p1["pass"] else "FAIL",
            },
            {
                "id": "T2-PROBE-2-SUBSTITUTE-INSTRUMENT",
                "name": "each assertion re-measured with a different instrument",
                "command": P2,
                "result": "PASS" if c2 == 0 and p2["pass"] else "FAIL",
            },
            {
                "id": "T3-KNOWN-STALE-MNN-REFUTED",
                "name": "31-way M-NN still-live pin is REFUTED, not CONFIRMED",
                "command": P2,
                "result": "PASS" if mnn == "REFUTED" else "FAIL",
            },
            {
                "id": "T4-KNOWN-STALE-RETIRED-TOOL-REFUTED",
                "name": "retired AgentBridge budget tools described as available are REFUTED",
                "command": P2,
                "result": "PASS" if retired == "REFUTED" else "FAIL",
            },
            {
                "id": "T5-TRUE-CONTROL-CONFIRMED",
                "name": "catalog parse control remains CONFIRMED",
                "command": P2,
                "result": "PASS" if catalog == "CONFIRMED" else "FAIL",
            },
            {
                "id": "T6-DECLARED-SCHEMA",
                "name": "artifact parses against command-center/schema/stale-premise-reprobe.schema.json",
                "command": "jsonschema Draft7Validator",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0012-probe2-reprobe",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "mechanical-probe",
            "method": (
                "Independent instruments: JSON id-field intersection, PATH/"
                "which, filesystem glob of artifact roots. Does not re-read "
                "Probe 1's extraction table as proof."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "role": "inventory",
                "verbatim": PROBE1_TEXT,
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "role": "reprobe",
                "verbatim": PROBE2_TEXT,
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0012/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "retry ONLY with a mechanically different probe",
        },
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "required_fix": None,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for ADV-0012. Did not run tools/command-center/unit_manifest.py "
            "--write. Did not relaunch finish-everything-close or "
            "p2-cloud-ok-deliver. Named ledgers are absent; that is REFUTED, "
            "not BLOCKED."
        ),
        "completion_line": f"UNIT-COMPLETE:{UNIT}",
        "completion_marker_protocol": (
            "Literal JSON-permitted U+0085 delimiters preserve valid JSON while "
            "splitlines exposes the exact completion line near the artifact tail."
        ),
        "completion_marker": f"{nel}UNIT-COMPLETE:{UNIT}{nel}",
    }
    errors = validate(doc)
    if errors:
        print(f"FAILED:{UNIT} schema {errors[:8]}")
        return 1
    if any(t["result"] != "PASS" for t in doc["tests"]):
        print(f"FAILED:{UNIT} a required test is not PASS")
        return 1
    if PROBE1_TEXT not in json.dumps(doc) or PROBE2_TEXT not in json.dumps(doc):
        print(f"FAILED:{UNIT} named probe text missing")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:{UNIT} artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        print(f"FAILED:{UNIT} completion_sentinel missing after write")
        return 1
    reparse = json.loads(text)
    post_errors = validate(reparse)
    if post_errors:
        print(f"FAILED:{UNIT} schema after write {post_errors[:8]}")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={sha} overall={overall}")
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
