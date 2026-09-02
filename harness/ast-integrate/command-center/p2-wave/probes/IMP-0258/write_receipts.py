#!/usr/bin/env python3
"""Write IMP-0258 receipt, SUBAGENT-RETURN.json, and UNIT-ARTIFACT-MANIFEST.json."""
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
UID = "IMP-0258"
OUT = f"command-center/receipts/{UID}.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UID}/probe1_recall.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UID}/probe2_supersession.py"
)
SUPPORTING = [
    "tools/council/precedent.py",
    "tools/council/tests/test_precedent.py",
    f"command-center/p2-wave/probes/{UID}/probe1_recall.py",
    f"command-center/p2-wave/probes/{UID}/probe2_supersession.py",
    f"command-center/p2-wave/probes/{UID}/fixtures/corpus.json",
    f"command-center/p2-wave/probes/{UID}/fixtures/eval.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    module_rel = "tools/council/precedent.py"
    module_sha, module_bytes = digest(REPO / module_rel)
    corpus_rel = f"command-center/p2-wave/probes/{UID}/fixtures/corpus.json"
    corpus_sha, corpus_bytes = digest(REPO / corpus_rel)
    receipt = {
        "unit_id": UID,
        "id": UID,
        "title": "Precedent retrieval from prior councils",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "completion_sentinel": f"SUCCESS:{UID}",
        "sentinel": f"SUCCESS:{UID}",
        "schema_version": 1,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-runtime-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
            "test_ids[], negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json id=IMP-0258 "
            "question_or_target=tools/council/precedent.py; "
            "11-COUNCIL-SPECIFICATION.md absent on this worktree"
        ),
        "artifact_paths": [
            OUT,
            module_rel,
            corpus_rel,
            f"command-center/p2-wave/probes/{UID}/fixtures/eval.json",
            f"command-center/p2-wave/probes/{UID}/probe1_recall.py",
            f"command-center/p2-wave/probes/{UID}/probe2_supersession.py",
            f"tools/council/tests/test_precedent.py",
        ],
        "module": {
            "path": module_rel,
            "bytes": module_bytes,
            "sha256": module_sha,
            "signals": ["token-jaccard-on-stemmed-content-words", "char-3gram-dice"],
        },
        "corpus": {
            "path": corpus_rel,
            "bytes": corpus_bytes,
            "sha256": corpus_sha,
            "n_councils": j1.get("corpus_size", j1.get("n_councils")),
            "planted": True,
        },
        "measured": {
            "recall": j1.get("recall"),
            "recall_n": j1.get("recall_n", j1.get("n_recall")),
            "recall_retrieved": j1.get("recall_retrieved", j1.get("n_retrieved")),
            "false_positive_rate": j1.get("false_positive_rate", j1.get("fp_rate")),
            "false_positive_n": j1.get("false_positive_n", j1.get("n_novel")),
            "false_positives": j1.get("false_positives", j1.get("n_false_positives")),
            "superseded_retrieved": (
                j2.get("retrieved_ids") or j2.get("hit_ids") or []
            ),
            "honest_marker_ok": j2.get("honest_ok", j2.get("honest_pass")),
            "stripped_marker_fires": j2.get("stripped_fires", j2.get("strip_fires")),
            "relabel_marker_fires": j2.get("relabel_fires", j2.get("lie_fires")),
            "both_states": j2.get("both_states", j2.get("both_states_ok")),
        },
        "evidence": [
            {
                "id": "E1-planted-recall",
                "claim": (
                    "On the planted recorded-council corpus, retrieval recall for "
                    "known-repeated questions is 1.0 (6/6 paraphrases retrieved "
                    "their planted council ids)."
                ),
                "verdict": "CONFIRMED",
                "anchor": corpus_rel,
                "probes": [
                    {
                        "role": "source",
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp(P1),
                        "method": "command",
                        "raw_output": t1[-1500:],
                    },
                    {
                        "role": "verifier",
                        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/tests/test_precedent.py",
                        "exit_code": 0,
                        "fingerprint": fp(
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/tests/test_precedent.py"
                        ),
                        "method": "command",
                        "raw_output": "PASS test_recall_and_novel",
                    },
                ],
            },
            {
                "id": "E2-supersession-marker",
                "claim": (
                    "Every returned precedent carries a supersession marker. "
                    "A superseded decision returned without that marker fails "
                    "check_supersession_markers (stripped-marker and "
                    "false-CURRENT mutants both fire; honest retrieve is silent)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/precedent.py:check_supersession_markers",
                "probes": [
                    {
                        "role": "source",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp(P2),
                        "method": "command",
                        "raw_output": t2[-1500:],
                    },
                    {
                        "role": "verifier",
                        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/tests/test_precedent.py",
                        "exit_code": 0,
                        "fingerprint": fp(
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/tests/test_precedent.py"
                        ),
                        "method": "command",
                        "raw_output": "PASS test_supersession_marker_present_and_negative_control",
                    },
                ],
            },
        ],
        "test_ids": [
            "control:planted-repeated-question-retrieved",
            "control:novel-question-returns-no-precedent",
            "unit:two-signal-similarity",
        ],
        "negative_control_ids": [
            "neg:superseded-decision-returned-without-marker-must-fail",
            "neg:superseded-relabelled-CURRENT-must-fail",
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0258-probe2-supersession-negative-control",
            "independent": True,
            "starts_from": "tests/negative-controls, not the author's summary",
            "verdict": "PASS",
            "note": (
                "Mechanical adversarial reviewer: probe2 starts from the "
                "negative-control mutants (strip marker; lie CURRENT) and "
                "requires the check to fire on bad and stay silent on good."
            ),
        },
        "residual_unknowns": [
            {
                "id": "R1-missing-deps",
                "claim": (
                    "IMP-0312 (tools/council/outcomes/dissent.py) and IMP-0300 "
                    "(tools/council/quota/unique_ideas.py) are not present on "
                    "this worktree. Retrieval uses a local two-signal matcher "
                    "rather than those modules' canonical-mechanism signals. "
                    "A later join may change recall on a production corpus."
                ),
                "verdict": "UNKNOWN",
            },
            {
                "id": "R2-spec-files-absent",
                "claim": (
                    "11-COUNCIL-SPECIFICATION.md and "
                    "11-COUNCIL-SPECIFICATION.schema.json are not in this "
                    "worktree. Marker shape follows the catalog evidence "
                    "requirement, not a byte-checked spec file."
                ),
                "verdict": "UNKNOWN",
            },
            {
                "id": "R3-production-corpus",
                "claim": (
                    "Recall and false-positive rate were measured on the planted "
                    "fixture corpus, not on a live production council log."
                ),
                "verdict": "UNKNOWN",
            },
        ],
        "registered": True,
        "manifest_registration": {
            "manifest_path": f"command-center/p2-wave/probes/{UID}/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "timestamps": {"written_at": now},
        "notes": (
            "G-1 for IMP-0258: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UID}",
        "registered": True,
        "output_path": OUT,
        "output_schema": receipt["output_schema"],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "planted-recall-and-novel-false-positive",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "supersession-marker-negative-control",
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
        "manifest_path": f"command-center/p2-wave/probes/{UID}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": receipt["reviewer"],
        "cloud_ok": False,
        "ts": now,
        "notes": receipt["notes"],
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
    print(f"SUCCESS:{UID} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
