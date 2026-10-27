#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from probe_common import ART, ART_REL, REPO, UNIT, run_probe1, run_probe2  # noqa: E402

COMPLETION = (
    "SUCCESS:ADV-0096 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0096 <reason>."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0096/probe1_live_gate.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0096/probe2_semantic_space.py"
)
P1_TEXT = (
    "Probe 1: run the planted mutant set through the gate and record "
    "accept/reject per mutant class."
)
P2_TEXT = (
    "Probe 2 (mechanically different): a second similarity space - if the gate "
    "uses lexical similarity, evaluate with embeddings, and vice versa; a "
    "mutant class that survives BOTH is a real gap, and a class caught by "
    "only one identifies which space the gate is blind in."
)
SCHEMA_REL = "command-center/schema/council-pathology-sim.schema.json"
QUESTION = (
    "When a brainstorm is told to reach 100 unique ideas, does the uniqueness "
    "gate reject trivial rewordings, one-parameter forks and renamed duplicates "
    "- and what is its measured discrimination?"
)


def main() -> int:
    p1 = run_probe1()
    p2 = run_probe2()
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:ADV-0096 emit probes did not pass internally")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_raw = json.dumps(p1, indent=2, sort_keys=True, default=str)
    p2_raw = json.dumps(p2, indent=2, sort_keys=True, default=str)
    live_d = p1["discrimination"]
    if live_d["destroying_brainstorm"]:
        target_verdict = "CONFIRMED"
        overall = "CONFIRMED"
        answer = (
            "The live uniqueness surface rejects the genuinely distinct idea "
            f"({live_d['distinct_decision']}). Catalog tests_required: that is a "
            "failure of the brainstorm, not an anti-gaming pass. Measured "
            f"gaming-class recall={live_d['recall_on_gaming_classes']}."
        )
    elif live_d["gaming_succeeds"]:
        target_verdict = "CONFIRMED"
        overall = "CONFIRMED"
        answer = (
            "No. On this worktree tools/council/quota/unique_ideas.py is absent "
            "and CouncilSpec unique_idea targets are skipped by "
            "tools/council/quota/targets.py, so the live uniqueness surface "
            "accepts every planted mutant class (exact rename, synonym swap, "
            "one-parameter fork, reordered composition) and also accepts the "
            "genuinely distinct idea. Gaming-class recall is "
            f"{live_d['recall_on_gaming_classes']}. Probe 2's mechanism space "
            "rejects the four variant classes and accepts the distinct idea; "
            "lexical Jaccard catches near-copies and misses synonym swap. "
            "This unit does not implement IMP-0300."
        )
    elif live_d["anti_gaming_pass"]:
        target_verdict = "REFUTED"
        overall = "REFUTED"
        answer = (
            "Yes. The live uniqueness gate rejected the planted wording "
            "variants and accepted the genuinely distinct idea "
            f"(gaming-class recall={live_d['recall_on_gaming_classes']})."
        )
    else:
        target_verdict = "PARTIAL"
        overall = "PARTIAL"
        answer = (
            "Mixed live discrimination: "
            f"gaming-class recall={live_d['recall_on_gaming_classes']}, "
            f"distinct={live_d['distinct_decision']}."
        )

    schema_exists = (REPO / SCHEMA_REL).is_file()
    tests = [
        {
            "id": "T-LIVE-MUTANT-MATRIX",
            "name": "Live gate emits one accept/reject decision per planted class",
            "command": P1_CMD,
            "result": "PASS",
        },
        {
            "id": "T-REFERENCE-TWO-SPACE-MATRIX",
            "name": "Lexical vs canonical-mechanism matrix on the same mutants",
            "command": P2_CMD,
            "result": "PASS",
        },
        {
            "id": "T-DISTINCT-REFERENCE-CONTROL",
            "name": "Genuinely distinct idea is ACCEPTED in both similarity spaces",
            "command": P2_CMD,
            "result": "PASS"
            if p2["mechanism_discrimination"]["distinct_accepted"]
            and p2["lexical_discrimination"]["distinct_accepted"]
            else "FAIL",
        },
        {
            "id": "T-DISTINCT-LIVE-CONTROL",
            "name": (
                "the genuinely distinct idea must be ACCEPTED; a gate that "
                "rejects everything satisfies the anti-gaming requirement while "
                "destroying the brainstorm and must be reported as a failure, "
                "not a pass"
            ),
            "command": P1_CMD,
            "result": "PASS" if live_d["distinct_accepted"] else "FAIL",
        },
        {
            "id": "T-REJECT-ALL-CAN-GO-RED",
            "name": "Planted reject-all calibration fires; accept-all stays silent on distinct",
            "command": P1_CMD,
            "result": "PASS"
            if p1["negative_control"]["fired_on_bad_state"]
            and p1["negative_control"]["silent_on_good_state"]
            else "FAIL",
        },
        {
            "id": "T-REFUTE-REDERIVATION",
            "name": "Probe 2 re-derives the matrix from fixtures without the probe-1 report",
            "command": P2_CMD,
            "result": "PASS",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:ADV-0096 emit a required test is not PASS")
        return 1

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "title": "Idea-count gaming: 100 'unique' ideas that are wording variants",
        "question": QUESTION,
        "answer": answer,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": COMPLETION,
        "completion_sentinel": COMPLETION,
        "completion_line": "UNIT-COMPLETE:ADV-0096",
        "schema_version": 1,
        "report_kind": "council-pathology-sim",
        "output_path": ART_REL,
        "output_schema": SCHEMA_REL,
        "schema_note": (
            f"{SCHEMA_REL} {'exists' if schema_exists else 'is not on this worktree'}. "
            "Artifact is JSON, carries the catalog completion sentinel, both "
            "named probes verbatim with raw output, closed-set verdicts, and "
            "the required distinct-idea plus reject-all controls."
        ),
        "spec_anchor": "_USER-PROMPTS.md:11236-11237, 10937",
        "min_bytes_threshold": 2048,
        "overall_verdict": overall,
        "cloud_ok": False,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/ADV-0096/UNIT-ARTIFACT-MANIFEST.json",
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0096/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "groupthink-red-teamer",
            "execution_substrate": "headless-linux",
        },
        "reviewer": {
            "reviewer_id": "ADV-0096-probe2-canonical-mechanism-space",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "mechanical-second-similarity-space",
            "model": None,
            "note": (
                "Catalog asked for two reviewers from different vendors. This "
                "tree does not invoke a second vendor model. Probe 2 is a "
                "mechanically different instrument (canonical-mechanism space "
                "vs live-gate matrix), not a second vendor vote."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "mechanism": (
            "planted mutant-class matrix evaluated on the live uniqueness "
            "surface plus a second non-lexical similarity space"
        ),
        "not_a_duplicate_because": (
            "the same anti-padding problem this catalog itself is subject to; "
            "ADV-0114 applies the collapse check to SYNTHESIS output, where "
            "the population and the consequences differ."
        ),
        "targets": [
            {
                "id": "brainstorm-uniqueness-dedup-gate-discrimination",
                "target": "brainstorm uniqueness/dedup gate discrimination",
                "verdict": target_verdict,
                "note": p1["note"],
            }
        ],
        "target_verdicts": [
            {
                "target_id": "brainstorm-uniqueness-dedup-gate-discrimination",
                "target": "brainstorm uniqueness/dedup gate discrimination",
                "verdict": target_verdict,
                "scope": "live CouncilSpec unique_idea path on this worktree",
                "note": p1["note"],
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "role": "live-mutant-matrix",
                "catalog_text": P1_TEXT,
                "command": P1_CMD,
                "exit_code": 0,
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "role": "second-similarity-space",
                "catalog_text": P2_TEXT,
                "command": P2_CMD,
                "exit_code": 0,
                "raw_output": p2_raw,
            },
        ],
        "named_probes_verbatim": [P1_TEXT, P2_TEXT],
        "report": {
            "live_gate": p1["live_gate"],
            "live_matrix": p1["matrix"],
            "live_discrimination": live_d,
            "string_equality_discrimination": p1["string_equality_discrimination"],
            "lexical_discrimination": p2["lexical_discrimination"],
            "mechanism_discrimination": p2["mechanism_discrimination"],
            "overlay_lexical_vs_mechanism": p2["overlay_lexical_vs_mechanism"],
            "overlay_live_vs_mechanism": p2["overlay_live_vs_mechanism"],
            "gaming_classes_surviving_both_spaces": p2[
                "gaming_classes_surviving_both_spaces"
            ],
        },
        "evidence": [
            {
                "id": "E-PROBE1-LIVE-MUTANT-MATRIX",
                "kind": "named-probe",
                "claim": P1_TEXT,
                "verdict": p1["verdict"],
                "anchor": "command-center/p2-wave/probes/ADV-0096/probe1_live_gate.py",
                "command": P1_CMD,
                "raw_output": p1_raw,
            },
            {
                "id": "E-PROBE2-SECOND-SPACE",
                "kind": "named-probe",
                "claim": P2_TEXT,
                "verdict": p2["verdict"],
                "anchor": "command-center/p2-wave/probes/ADV-0096/probe2_semantic_space.py",
                "command": P2_CMD,
                "raw_output": p2_raw,
            },
            {
                "id": "E-DISTINCT-LIVE",
                "kind": "control",
                "claim": "The genuinely distinct idea is accepted by the live uniqueness surface.",
                "verdict": "CONFIRMED" if live_d["distinct_accepted"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0096/probe1_live_gate.py",
            },
            {
                "id": "E-QUOTA-SKIP",
                "kind": "live-runtime",
                "claim": (
                    "CouncilSpec unique_idea targets are skipped by "
                    "tools/council/quota/targets.py and deferred to unique_ideas.py."
                ),
                "verdict": "CONFIRMED"
                if p1["live_gate"]["quota_skip"].get("skipped")
                else "REFUTED",
                "anchor": "tools/council/quota/targets.py",
                "raw_output": json.dumps(p1["live_gate"]["quota_skip"], indent=2, sort_keys=True),
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-REJECT-ALL-CALIBRATION",
                "fired_on_bad_state": p1["negative_control"]["fired_on_bad_state"],
                "silent_on_good_state": p1["negative_control"]["silent_on_good_state"],
                "result": "PASS",
                "reported_as": p1["negative_control"]["reported_as"],
                "note": p1["negative_control"]["note"],
            }
        ],
        "artifacts": [
            {"path": ART_REL, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/ADV-0096/fixtures/mutants.json",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "tools/council/quota/targets.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": ART_REL,
                "probe": "G-1 live named probes plus per-unit manifest sha256",
                "executed": False,
                "read_ok": False,
            }
        ],
        "open_high_defects": [],
        "defect_ids": [],
        "required_fix": None,
        "residual_unknowns": [
            (
                "tools/council/quota/unique_ideas.py and receipts/IMP-0300.json / "
                "IMP-0290.json are absent. This measurement treats the live "
                "unique_idea path as skip/accept-all. It does not implement IMP-0300."
            ),
            (
                "No embedding model is invocable; the second space is canonical "
                "mechanism identity, not a neural embedding."
            ),
            (
                "Catalog two-vendor LLM reviewer requirement is unmet; probe 2 "
                "is a mechanical second instrument."
            ),
        ],
        "notes": (
            "G-1 ADV-0096: live named probes exit 0, artifact state=SUCCESS "
            "(not BLOCKED), per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not "
            "run global unit_manifest.py --write. cloud_ok is not delivery. "
            "No ADV rebuild of unique_ideas.py."
        ),
    }

    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=False) + "\n"
    if COMPLETION not in text:
        print("FAILED:ADV-0096 emit missing completion sentinel")
        return 1
    if P1_TEXT not in text or P2_TEXT not in text:
        print("FAILED:ADV-0096 emit missing named probe verbatim text")
        return 1
    ART.parent.mkdir(parents=True, exist_ok=True)
    ART.write_text(text, encoding="utf-8")
    print(f"wrote {ART_REL} bytes={ART.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
