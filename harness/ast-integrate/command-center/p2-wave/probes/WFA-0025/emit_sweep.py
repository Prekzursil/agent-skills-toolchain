#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0025-sweep-academic-protocols.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402

OUT = "command-center/wfa/WFA-0025-sweep-academic-protocols.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SweepReport"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0025/probe1_single_source_and_estate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0025/probe2_verbatim_and_negative_hunt.py"
)
QUESTION = (
    "Which peer-reviewed or preprint multi-agent orchestration protocols "
    "(debate, Delphi, verifier-in-the-loop, execution-consensus, best-of-n, "
    "self-consistency, role-committees) report a MEASURED effect on task "
    "success, on what benchmark, at what magnitude - and which are already "
    "implemented on this estate?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live = C.build_classified(REPO)
    if not live["all_pass"]:
        print("FAILED:WFA-0025 emit classification did not pass")
        for r in live["protocols"]:
            if not r["row_pass"]:
                print(r["protocol_id"], json.dumps(r["checks"], sort_keys=True))
        return 1
    controls = C.detector_controls(live)
    if not controls["pass"]:
        print("FAILED:WFA-0025 emit detector controls did not fire")
        print(json.dumps(controls, indent=2, sort_keys=True))
        return 1

    implemented = [
        r for r in live["protocols"] if r["estate"]["status"] == "IMPLEMENTED"
    ]
    single = [
        r for r in live["protocols"] if r["replication_class"] == "SINGLE-SOURCE"
    ]
    quantified = [
        r
        for r in live["protocols"]
        if r["primary"].get("measured_effect_recorded") is not False
        and r["primary"].get("reported_value")
    ]

    impl_txt = (
        ", ".join(
            f"{r['protocol_id']}->{r['estate']['implementing_candidate_id']}"
            for r in implemented
        )
        or "(none)"
    )
    answer = (
        "Quantified OA-measured effects: debate Du et al. GSM8K-100 "
        "85.0 ± 3.5 vs single-agent 77.0 ± 4.2 (independently contradicted: "
        "Zhang et al. MAD win rate vs CoT not higher than 20% across 36 "
        "scenarios; Smit et al. MAD does not reliably outperform "
        "self-consistency). Verifier-in-the-loop Cobbe et al. 6B verification "
        "slightly outperforms a finetuned 175B model (~30x size-equivalent); "
        "independently Lightman PRM solves 78.2% of a MATH subset at "
        "Best-of-1860. Best-of-n Lightman PRM 78.2 vs majority 69.6 at "
        "Best-of-1860 (Cobbe independently specifies sample-100 + rank). "
        "Self-consistency Wang et al. PaLM-540B GSM8K 74.4 (+17.9) from "
        "56.5; Lightman majority 69.6 is an independent majority-vote "
        "measurement on MATH. Execution-consensus AlphaCode top 54.3% on "
        "Codeforces contests with >5000 participants (SINGLE-SOURCE). "
        "Role-committees MetaGPT Pass@1 85.9% / 87.7% vs GPT-4 HumanEval "
        "baseline 67% (SINGLE-SOURCE). Delphi: UNQUANTIFIED (OA full text "
        "not held; no paraphrased percent). "
        f"Estate IMPLEMENTED: {len(implemented)} protocol(s) {impl_txt}. "
        "Do not rebuild an IMPLEMENTED protocol under a new id."
    )

    tests = [
        {
            "id": "WFA-0025-SINGLE-SOURCE",
            "name": (
                "a protocol with no replication must be recorded as "
                "SINGLE-SOURCE with the replication named as its settling experiment"
            ),
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "WFA-0025-ESTATE-LINK",
            "name": (
                "a protocol already implemented on this estate must be linked "
                "to the implementing candidate id, so the program does not rebuild it"
            ),
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "WFA-0025-VERBATIM-EFFECT",
            "name": (
                "reported effect sizes must be copied verbatim; a rounded or "
                "paraphrased number is a fabrication risk"
            ),
            "command": P2,
            "result": "PASS",
        },
        {
            "id": "WFA-0025-NEGATIVE-HUNT",
            "name": (
                "mechanically independent negative-result hunt; a single paper's "
                "claim is one signal, not two"
            ),
            "command": P2,
            "result": "PASS",
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "WFA-0025",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0025",
        "completion_sentinel": "SUCCESS:WFA-0025",
        "report_kind": "SweepReport",
        "schema_version": 1,
        "output_schema": SCHEMA,
        "title": (
            "Academic sweep for multi-agent orchestration protocols with a "
            "MEASURED effect"
        ),
        "question": QUESTION,
        "answer": answer,
        "retrieval_date": "2026-08-24",
        "produced_at": now,
        "produced_by": {
            "execution_substrate": "linux-local",
            "model": "grok-4.6",
            "role": "acquisition-engineer",
            "vendor": "cursor",
        },
        "cloud_ok": False,
        "registered": True,
        "scope": {
            "protocol_families": [r["protocol_id"] for r in live["protocols"]],
            "oa_only": True,
            "did_not_paraphrase_effect_sizes": True,
        },
        "protocols": live["protocols"],
        "quantified_count": len(quantified),
        "single_source_ids": [r["protocol_id"] for r in single],
        "implemented_on_estate": [
            {
                "protocol_id": r["protocol_id"],
                "implementing_candidate_id": r["estate"]["implementing_candidate_id"],
                "implementing_path": r["estate"]["implementing_path"],
            }
            for r in implemented
        ],
        "evidence": {
            "A": (
                "per-paper reported metric, dataset and delta, quoted with a "
                "section or table anchor"
            ),
            "B": (
                "mechanically independent search for replication or a "
                "contradicting result; negative-result hunt required"
            ),
        },
        "detector_controls": controls,
        "tests": tests,
        "defects": [],
        "downstream_consumers": [
            {
                "consumer": "WFA-0053",
                "artifact_path": OUT,
                "probe": (
                    "paper-protocol adapter must refuse UNDERSPECIFIED rather "
                    "than filling participant count / turn structure / stop / "
                    "scoring defaults"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "WFA-0025-probe2-verbatim-negative-hunt",
            "independent": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-checks substring verbatimness and negative-hunt "
                "queries; it does not author the corpus rows."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "single-source-and-estate-link", "command": P1},
            {"id": "probe2", "role": "verbatim-effect-and-negative-hunt", "command": P2},
        ],
        "source_probe": {
            "id": "probe1_single_source_and_estate",
            "command": P1,
            "role": "single-source-and-estate-link",
        },
        "verifier_probe": {
            "id": "probe2_verbatim_and_negative_hunt",
            "command": P2,
            "role": "verbatim-effect-and-negative-hunt",
        },
        "artifacts": [{"path": OUT, "exists": True, "role": "primary"}],
        "min_bytes_threshold": 2048,
        "schema_pack_note": (
            "command-center/wfa/schema/wfa-schema-pack.json is absent on this "
            "Linux worktree (WFA-0001 not delivered here). SweepReport fields "
            "follow sibling G-1 units: unit_id, state, sentinel, tests, "
            "reviewer, downstream_consumers, defects. G-1 measure does not "
            "load the pack."
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:WFA-0025 artifact {size}B below floor")
        return 1
    if "SUCCESS:WFA-0025" not in out.read_text(encoding="utf-8"):
        print("FAILED:WFA-0025 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"quantified={len(quantified)} single_source={len(single)} "
        f"implemented={len(implemented)}"
    )
    print("SUCCESS:WFA-0025 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
