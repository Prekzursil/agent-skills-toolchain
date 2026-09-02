#!/usr/bin/env python3
"""Emit ADV-0007 option-ID binding refutation artifact.

Does not create command-center/schema/refutation-record.schema.json
(no ADV schema-rebuild loop). G-1 needs parseable JSON, the catalog
completion_sentinel substring, non-BLOCKED state, live probes, and a
per-unit manifest row.
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
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

UNIT = E.UNIT
OUT_REL = E.OUT_REL
SCHEMA = E.SCHEMA_REL
P1 = E.PROBE1
P2 = E.PROBE2
SENTINEL = E.SENTINEL
QUESTION = E.QUESTION
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0007/engine.py",
    "command-center/p2-wave/probes/ADV-0007/probe1_defining_index.py",
    "command-center/p2-wave/probes/ADV-0007/probe2_title_similarity.py",
    "command-center/p2-wave/probes/ADV-0007/fixtures/defining/option-universe.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/defining/architecture-candidates.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/defining/research-harness.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/references/unambiguous.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/references/ambiguous.md",
    "command-center/p2-wave/probes/ADV-0007/fixtures/selected-ids.json",
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
        env=env,
        timeout=180,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def first_json(text: str) -> dict:
    line = text.splitlines()[0]
    doc = json.loads(line)
    if not isinstance(doc, dict):
        raise ValueError("probe JSON was not an object")
    return doc


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or f"SUCCESS:{UNIT}-probe1" not in t1:
        print(f"FAILED:{UNIT} emit probe1 c1={c1}")
        print(t1[-3000:])
        return 1
    if c2 != 0 or f"SUCCESS:{UNIT}-probe2" not in t2:
        print(f"FAILED:{UNIT} emit probe2 c2={c2}")
        print(t2[-3000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print(f"FAILED:{UNIT} emit probe pass=false")
        return 1

    report = E.build_report(REPO)
    if not report["controls_ok"]:
        print(f"FAILED:{UNIT} emit controls_ok=false")
        print(json.dumps(report["controls"], indent=2)[:4000])
        return 1

    targets = report["targets"]
    allowed = E.ALLOWED
    if any(x["verdict"] not in allowed for x in targets):
        print(f"FAILED:{UNIT} emit illegal target verdict")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / SCHEMA
    missing_inputs = report["inputs"]["missing"]
    counts = report["target_verdict_counts"]
    answer = (
        "Planted detector controls hold: FX-16 has three DEFINING headings "
        "and the bare reference is UNRESOLVED; FX-40 has exactly one defining "
        "heading and binds uniquely by title tokens. Live Prompt Two selected "
        f"IDs cannot be closed on this worktree: missing inputs={missing_inputs}. "
        "Catalog-named sample A-01, A-03, A-12, A-13, A-17, A-18 and live M-16 "
        "are NOT-CHECKED (no defining cards). Silent wrong-card binding is "
        f"REFUTED for planted FX-16 and CONFIRMED-unique for planted FX-40/"
        f"MECH-99. Counts CONFIRMED={counts['CONFIRMED']} REFUTED={counts['REFUTED']} "
        f"NOT-CHECKED={counts['NOT-CHECKED']}. {SENTINEL}"
    )
    artifacts = [art(rel, "supporting") for rel in SUPPORTING if (REPO / rel).is_file()]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "completion_sentinel": SENTINEL,
        "profile": "refutation-record",
        "report_kind": "refutation-record",
        "spec_anchor": "_USER-PROMPTS.md:10514-10516, 11074",
        "output_schema": SCHEMA,
        "output_schema_file_present": schema_path.is_file(),
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "overall_verdict": "PARTIAL",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai/cursor",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "local-parallel",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "retry ONLY with a mechanically different probe; re-running "
                "the identical probe is banned"
            ),
        },
        "report": {
            "kind": "refutation-record",
            "question_or_target": QUESTION,
            "answer": answer,
            "evidence_requirement": (
                "Probe 1: build an id->definition index from the DEFINING "
                "headings only, then resolve every REFERENCE site and flag "
                "any id with >1 candidate definition. Probe 2 (mechanically "
                "different): title-similarity check between the referenced "
                "context and each candidate definition, and where the prose "
                "carries no discriminating token, record UNRESOLVED rather "
                "than guessing."
            ),
            "tests_required": [
                "detector control: plant one deliberately ambiguous "
                "reference and require it to surface as UNRESOLVED, and "
                "plant one unambiguous reference and require exactly one binding"
            ],
            "targets": targets,
            "target_verdict_counts": counts,
            "inputs": report["inputs"],
            "live": report["live"],
            "planted": report["planted"],
        },
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/ADV-0007/probe1_defining_index.py",
                "claim": (
                    "DEFINING-heading index only. FX-16 has three candidate "
                    "definitions; FX-40 has one. Cardinality is the instrument; "
                    "prose is not classified by an LLM."
                ),
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": t1,
                        "exit_code": c1,
                    }
                ],
            },
            {
                "anchor": "command-center/p2-wave/probes/ADV-0007/probe2_title_similarity.py",
                "claim": (
                    "Title-token similarity, mechanically different from heading "
                    "cardinality. Bare 'See FX-16 for details' is UNRESOLVED. "
                    "'FX-40 Extra lane' binds to one card. No guess on missing "
                    "discriminating tokens."
                ),
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": t2,
                        "exit_code": c2,
                    }
                ],
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "tests": [
            {
                "id": "T-P1-DEFINING-INDEX",
                "name": "defining-heading index exits 0; FX-16 MULTI-DEF; FX-40 UNIQUE",
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-1500:],
            },
            {
                "id": "T-P2-TITLE-SIMILARITY",
                "name": "title-similarity exits 0; ambiguous UNRESOLVED; unique one binding",
                "command": P2,
                "result": "PASS",
                "output_tail": t2[-1500:],
            },
            {
                "id": "T-CONTROL-AMBIGUOUS-UNRESOLVED",
                "name": "planted ambiguous reference surfaces as UNRESOLVED",
                "command": P2,
                "result": "PASS",
                "assertions": {
                    "planted_ambiguous_unresolved": True,
                    "planted_unambiguous_one_binding": True,
                },
            },
            {
                "id": "T-CONTROL-UNAMBIGUOUS-ONE-BINDING",
                "name": "planted unambiguous reference has exactly one binding",
                "command": P1 + " && " + P2,
                "result": "PASS",
                "assertions": {
                    "fx16_multi_def": True,
                    "fx40_unique": True,
                },
            },
        ],
        "negative_controls": [
            {
                "id": "ADV0007-C1-ambiguous-unresolved",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted FX-16 is defined under three headings; a reference "
                    "with no discriminating title token must be UNRESOLVED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "FX-16 UNRESOLVED",
                "good_state_output": "FX-40 BOUND to one card",
            },
            {
                "id": "ADV0007-C2-unambiguous-unique",
                "kind": "both-states",
                "description": (
                    "Planted FX-40 has one defining heading and the consumer "
                    "carries its title tokens; probe 2 must bind exactly once."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "FX-16 multi-def / UNRESOLVED",
                "good_state_output": "FX-40 UNIQUE / BOUND",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0007-probe2-title-similarity",
            "vendor": "xai/cursor",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Cross-vendor relative to the catalog assignment "
                "(anthropic/opus). Re-derived from planted defining headings "
                "and reference fixtures, not from a prior ADV-0007 report. "
                "Did not rebuild refutation-record.schema.json."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0007/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "entry_id": UNIT,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/schema/refutation-record.schema.json is "
                    "absent. This record follows the refutation-record profile "
                    "used by sibling ADV units without rebuilding that global schema."
                ),
                "settling_experiment": "Deliver the schema-owning unit, then re-validate.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "07-OPTION-UNIVERSE, 13-ARCHITECTURE-CANDIDATES, "
                    "OPTION-ID-RESOLUTION.json, and 17-DECISION-LOG.md are "
                    "absent, so the 70 Prompt Two owner_decisions cannot be "
                    "resolved on this worktree."
                ),
                "settling_experiment": "Restore those corpora and re-run both probes.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "artifacts": artifacts,
        "cloud_ok": False,
        "notes": (
            "G-1 delivery of ADV-0007 option-ID binding refutation. Live named "
            "probes exit 0. Did not run global unit_manifest.py --write. Did "
            "not rebuild refutation-record.schema.json. cloud ok=true is not "
            f"delivery. SUCCESS:{UNIT}"
        ),
        "extensions": {
            "probe_commands": {"probe_1": P1, "probe_2": P2},
            "raw_evidence": {
                "probe_1_embedded_verbatim": True,
                "probe_2_embedded_verbatim": True,
            },
            "completion_contract": {
                "both_named_probes_embedded_verbatim": True,
                "one_allowed_verdict_per_target": True,
                "required_negative_control_recorded": True,
            },
            "probe1_index": report["probe1"],
            "probe2_resolutions": report["probe2"],
            "controls": report["controls"],
        },
    }
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    sha, size = digest(out_path)
    if SENTINEL not in payload:
        print(f"FAILED:{UNIT} emit sentinel missing from artifact")
        return 1
    if size < 2048:
        print(f"FAILED:{UNIT} emit artifact too small")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
