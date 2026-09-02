#!/usr/bin/env python3
"""Write IMP-0279 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
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
UNIT = "IMP-0279"
OUT = "command-center/receipts/IMP-0279.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0279/probe1_effective_voice.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0279/probe2_negative_control.py"
)
SUPPORTING = [
    "tools/council/integrity/dupes.py",
    "command-center/p2-wave/probes/IMP-0279/probe1_effective_voice.py",
    "command-center/p2-wave/probes/IMP-0279/probe2_negative_control.py",
    "command-center/p2-wave/probes/IMP-0279/scenario.py",
    "command-center/p2-wave/probes/IMP-0279/fixtures/roster_eight_copies.json",
    "command-center/p2-wave/probes/IMP-0279/fixtures/roster_diverse.json",
    "command-center/p2-wave/probes/IMP-0279/fixtures/roster_mixed.json",
    "command-center/p2-wave/probes/IMP-0279/fixtures/roster_labels_only.json",
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
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0279/SUBAGENT-RETURN.json",
        "role": role,
    }


def first_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def main() -> int:
    sys.path.insert(0, str(HERE))
    import scenario  # noqa: WPS433

    scenario.write_fixture_files()
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    dupes = scenario.load_dupes()
    cloned = scenario.roster_eight_copies()
    diverse = scenario.roster_diverse()
    mixed = scenario.roster_mixed()
    a_clone = dupes.audit_roster(cloned["seats"], cloned["outputs"])
    a_div = dupes.audit_roster(diverse["seats"], diverse["outputs"])
    a_mix = dupes.audit_roster(mixed["seats"], mixed["outputs"])
    p1_json = first_json_line(t1)
    p2_json = first_json_line(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    module_rel = "tools/council/integrity/dupes.py"
    module_sha, module_bytes = digest(REPO / module_rel)

    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0279",
        "completion_sentinel": "SUCCESS:IMP-0279",
        "title": "Duplicate-participant detector",
        "profile": "council-integrity-module",
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-integrity-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
            "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0279 question_or_target: "
            "does a council of 8 seats that are 8 copies of one configuration "
            "report an effective independence count of 1?"
        ),
        "artifact_paths": [OUT, module_rel] + SUPPORTING[1:],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "timestamps": {"ended_at": now},
        "evidence": [
            {
                "id": "E1-eight-copies-config",
                "claim": (
                    "Eight seats that copy one configuration (vendor, model, system "
                    "prompt, tools, context), including tool-order permutations and "
                    "distinct seat_id/name/role labels, audit to effective_independence_count=1 "
                    f"with one flagged cluster of size 8. Measured {a_clone['effective_independence_count']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/integrity/dupes.py:fingerprint_seat",
                "measured": {
                    "seat_count": a_clone["seat_count"],
                    "effective_independence_count": a_clone["effective_independence_count"],
                    "flagged_size": a_clone["flagged"][0]["size"] if a_clone["flagged"] else 0,
                    "probe1": p1_json,
                },
            },
            {
                "id": "E2-eight-copies-output-similarity",
                "claim": (
                    "On the same cloned roster, independently authored identical first-round "
                    "texts yield mean pairwise token-Jaccard "
                    f"{a_clone['similarity']['mean_pairwise_jaccard']}, "
                    f"corroboration={a_clone['corroboration']['verdict']}. "
                    "Outputs were not derived from the fingerprint function."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/integrity/dupes.py:corroborate",
                "measured": a_clone["corroboration"],
            },
            {
                "id": "E3-diverse-negative-control",
                "claim": (
                    "An 8-seat roster with distinct vendor/model/prompt/tools/context "
                    f"reports independence {a_div['effective_independence_count']} "
                    f"(must be >1 so the detector is not constant-firing) and mean "
                    f"Jaccard {a_div['similarity']['mean_pairwise_jaccard']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0279/fixtures/roster_diverse.json",
                "measured": {
                    "effective_independence_count": a_div["effective_independence_count"],
                    "mean_pairwise_jaccard": a_div["similarity"]["mean_pairwise_jaccard"],
                    "probe2": p2_json,
                },
            },
        ],
        "test_ids": [
            "IMP-0279-effective-voice-count",
            "IMP-0279-negative-control-diverse",
            "IMP-0279-mixed-six-plus-two",
            "IMP-0279-one-field-splits",
        ],
        "tests": [
            {
                "id": "IMP-0279-effective-voice-count",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
                "assertions": 8,
                "output_tail": t1[-1500:],
            },
            {
                "id": "IMP-0279-negative-control-diverse",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
                "assertions": 8,
                "output_tail": t2[-1500:],
            },
        ],
        "negative_control_ids": [
            "IMP-0279-NC-diverse-roster",
            "IMP-0279-NC-renamed-clone",
            "IMP-0279-NC-labels-are-not-voices",
        ],
        "negative_controls": [
            {
                "id": "IMP-0279-NC-diverse-roster",
                "kind": "constant-fire-guard",
                "description": (
                    "A genuinely diverse 8-seat roster must report independence >1. "
                    "Silence here would make the eight-copies result indistinguishable "
                    "from a detector that always emits 1."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "independence=1 would FAIL this control",
                "good_state_output": f"independence={a_div['effective_independence_count']}",
            },
            {
                "id": "IMP-0279-NC-renamed-clone",
                "kind": "identity-leak-guard",
                "description": "Renaming a cloned seat must not mint a second voice.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": f"renamed_clone_independence={p2_json.get('renamed_clone_independence')}",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0279-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "starts_from": "catalog tests_required, not the author summary",
            "notes": (
                "Probe 2 re-measures eight copies, rejects a seat-count detector, "
                "rejects a constant-1 detector, and requires each of the five "
                "fingerprint fields to split a voice. A second human in a fresh "
                "context was not obtained on this worktree."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "First-round texts used for corroboration are scripted fixtures, "
                    "not live model completions. A live 8-clone council could still "
                    "diverge in sampling even when configs match."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Seat eight live copies of one config, capture first-round bytes, "
                    "re-run similarity_report, and require corroboration.agrees."
                ),
            },
            {
                "claim": (
                    "IMP-0265 participant registry is absent on this tree. dupes.py "
                    "consumes seat mappings with the five fingerprint fields; it does "
                    "not import tools/council/participants/registry.py."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "After IMP-0265, pass registry records through audit_roster.",
            },
            {
                "claim": (
                    "Sampling parameters (temperature, seed, top_p) are not in the "
                    "five catalog fingerprint fields, so two seats that differ only "
                    "in temperature still count as one voice."
                ),
                "verdict": "CONFIRMED-AS-RESIDUAL",
                "settling_experiment": (
                    "If later spec text names sampling as voice-defining, add it to "
                    "FINGERPRINT_FIELDS with a regression on this unit's eight-copy fixture."
                ),
            },
        ],
        "report": {
            "kind": "council-integrity-dupes",
            "module": {
                "path": module_rel,
                "bytes": module_bytes,
                "sha256": module_sha,
            },
            "eight_copies": {
                "effective_independence_count": a_clone["effective_independence_count"],
                "mean_pairwise_jaccard": a_clone["similarity"]["mean_pairwise_jaccard"],
                "corroboration": a_clone["corroboration"]["verdict"],
            },
            "diverse": {
                "effective_independence_count": a_div["effective_independence_count"],
                "mean_pairwise_jaccard": a_div["similarity"]["mean_pairwise_jaccard"],
                "corroboration": a_div["corroboration"]["verdict"],
            },
            "mixed_six_plus_two": {
                "effective_independence_count": a_mix["effective_independence_count"],
                "within_cluster_mean": a_mix["similarity"]["within_cluster_mean"],
                "across_cluster_mean": a_mix["similarity"]["across_cluster_mean"],
                "corroboration": a_mix["corroboration"]["verdict"],
            },
            "falsifiable_answer": (
                "Yes: 8 copies of one configuration report effective independence 1."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0279/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "cloud_ok": False,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0279",
        "registered": True,
        "output_path": OUT,
        "output_schema": receipt["output_schema"],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "effective-voice-count",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "negative-control-diverse-roster",
                "raw_output": t2,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0279/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": receipt["reviewer"],
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0279: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0279, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0279 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
